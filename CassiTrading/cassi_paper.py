"""Safe single-venue paper-trading runtime.

This module consumes closed MarketBar events, emits the existing shadow policy
intents, and settles them locally. It has no authenticated exchange path and no
live order side effect.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from cassi_market_contracts import Authority, Event, digest_value
from cassi_policy import PortfolioController, PortfolioPolicyConfig, PortfolioState, ProgramSignal
from cassi_trading_foundry import MarketBar, StrategyProgram, _features


PAPER_SCHEMA = "cassi.paper-session.v1"
PAPER_BAR_RECEIPT_SCHEMA = "cassi.paper-bar-receipt.v1"
PAPER_ACCOUNT_SCHEMA = "cassi.paper-account.v1"


class PaperTradingError(ValueError):
    """A paper session rejected invalid data, state, or a safety violation."""


def _finite(name: str, value: Any, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PaperTradingError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < minimum:
        raise PaperTradingError(f"{name} must be finite and >= {minimum}")
    return result


@dataclass(frozen=True, slots=True)
class PaperConfig:
    venue: str = "coinbase-public-paper"
    initial_cash: float = 10_000.0
    fee_bps: float = 10.0
    slippage_bps: float = 5.0
    max_position_fraction: float = 1.0
    max_turnover: float = 1.0
    max_drawdown: float = 0.20
    minimum_order_fraction: float = 1.0e-6
    allow_short: bool = False
    timeframe_seconds: int = 3600
    max_history: int = 512

    def __post_init__(self) -> None:
        _finite("initial_cash", self.initial_cash, minimum=1.0e-12)
        _finite("fee_bps", self.fee_bps)
        _finite("slippage_bps", self.slippage_bps)
        _finite("max_position_fraction", self.max_position_fraction)
        _finite("max_turnover", self.max_turnover)
        _finite("max_drawdown", self.max_drawdown)
        _finite("minimum_order_fraction", self.minimum_order_fraction)
        if self.max_drawdown >= 1.0:
            raise PaperTradingError("max_drawdown must be below 1")
        if isinstance(self.timeframe_seconds, bool) or not isinstance(self.timeframe_seconds, int) or self.timeframe_seconds < 1:
            raise PaperTradingError("timeframe_seconds must be a positive integer")
        if isinstance(self.max_history, bool) or not isinstance(self.max_history, int) or self.max_history < 32:
            raise PaperTradingError("max_history must be at least 32")
        if not isinstance(self.venue, str) or not self.venue.strip():
            raise PaperTradingError("venue must be nonempty text")

    def as_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "initial_cash": self.initial_cash,
            "fee_bps": self.fee_bps,
            "slippage_bps": self.slippage_bps,
            "max_position_fraction": self.max_position_fraction,
            "max_turnover": self.max_turnover,
            "max_drawdown": self.max_drawdown,
            "minimum_order_fraction": self.minimum_order_fraction,
            "allow_short": self.allow_short,
            "timeframe_seconds": self.timeframe_seconds,
            "max_history": self.max_history,
        }


@dataclass(slots=True)
class PaperAccount:
    cash: float
    positions: dict[str, float] = field(default_factory=dict)
    equity: float = 0.0
    peak_equity: float = 0.0
    fees_paid: float = 0.0
    frozen: bool = False
    last_timestamp: str | None = None
    last_prices: dict[str, float] = field(default_factory=dict)

    @classmethod
    def create(cls, initial_cash: float) -> "PaperAccount":
        return cls(cash=initial_cash, equity=initial_cash, peak_equity=initial_cash)

    def mark(self, bar: MarketBar) -> None:
        self.last_prices[bar.symbol] = bar.close
        self.last_timestamp = bar.timestamp
        self.equity = self.cash + sum(
            units * self.last_prices.get(symbol, bar.close)
            for symbol, units in self.positions.items()
        )
        self.peak_equity = max(self.peak_equity, self.equity)

    def exposure_fraction(self, symbol: str, price: float | None = None) -> float:
        mark = price if price is not None else self.last_prices.get(symbol)
        if mark is None or self.equity <= 0.0:
            return 0.0
        return self.positions.get(symbol, 0.0) * mark / self.equity

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": PAPER_ACCOUNT_SCHEMA,
            "cash": self.cash,
            "positions": dict(self.positions),
            "equity": self.equity,
            "peak_equity": self.peak_equity,
            "fees_paid": self.fees_paid,
            "frozen": self.frozen,
            "last_timestamp": self.last_timestamp,
            "last_prices": dict(self.last_prices),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "PaperAccount":
        if value.get("schema") != PAPER_ACCOUNT_SCHEMA:
            raise PaperTradingError("paper account schema mismatch")
        account = cls(
            cash=_finite("cash", value["cash"]),
            positions={str(k): float(v) for k, v in dict(value.get("positions", {})).items()},
            equity=_finite("equity", value["equity"]),
            peak_equity=_finite("peak_equity", value["peak_equity"]),
            fees_paid=_finite("fees_paid", value.get("fees_paid", 0.0)),
            frozen=bool(value.get("frozen", False)),
            last_timestamp=value.get("last_timestamp"),
            last_prices={str(k): float(v) for k, v in dict(value.get("last_prices", {})).items()},
        )
        if account.peak_equity < account.equity:
            raise PaperTradingError("paper account peak equity cannot trail equity")
        return account


@dataclass(frozen=True, slots=True)
class PaperFill:
    operation_id: str
    event_id: str
    symbol: str
    side: str
    quantity: float
    price: float
    notional: float
    fee: float
    timestamp: str
    position_after: float
    cash_after: float
    equity_after: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "operation_id": self.operation_id,
            "event_id": self.event_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "fee": self.fee,
            "timestamp": self.timestamp,
            "position_after": self.position_after,
            "cash_after": self.cash_after,
            "equity_after": self.equity_after,
        }


class PaperExecutionEngine:
    """Fill shadow intents locally with explicit fees, spread, and slippage."""

    def __init__(self, config: PaperConfig) -> None:
        self.config = config

    def execute_target(
        self,
        account: PaperAccount,
        bar: MarketBar,
        *,
        target_exposure: float,
        operation_id: str,
        event_id: str,
    ) -> PaperFill | None:
        target = max(-self.config.max_position_fraction, min(self.config.max_position_fraction, float(target_exposure)))
        if not self.config.allow_short and target < 0.0:
            raise PaperTradingError("short target rejected by paper safety policy")
        if account.frozen and target > 0.0:
            raise PaperTradingError("paper account is frozen after drawdown breach")
        account.mark(bar)
        current_units = account.positions.get(bar.symbol, 0.0)
        desired_units = target * account.equity / bar.close
        delta_units = desired_units - current_units
        if abs(delta_units * bar.close / max(account.equity, 1.0e-12)) < self.config.minimum_order_fraction:
            return None
        side = "buy" if delta_units > 0.0 else "sell"
        fill_price = bar.close * (1.0 + (1.0 if side == "buy" else -1.0) * self.config.slippage_bps / 10_000.0)
        quantity = abs(delta_units)
        fee_rate = self.config.fee_bps / 10_000.0
        if side == "buy":
            quantity = min(quantity, max(0.0, account.cash / (fill_price * (1.0 + fee_rate))))
        if quantity * bar.close / max(account.equity, 1.0e-12) < self.config.minimum_order_fraction:
            return None
        notional = quantity * fill_price
        fee = notional * fee_rate
        signed_units = quantity if side == "buy" else -quantity
        account.cash -= signed_units * fill_price + fee
        if account.cash < 0.0:
            if account.cash < -1.0e-8:
                raise PaperTradingError("paper cash became materially negative")
            account.cash = 0.0
        account.positions[bar.symbol] = current_units + signed_units
        account.fees_paid += fee
        account.mark(bar)
        if account.equity <= account.peak_equity * (1.0 - self.config.max_drawdown):
            account.frozen = True
        return PaperFill(
            operation_id=operation_id,
            event_id=event_id,
            symbol=bar.symbol,
            side=side,
            quantity=quantity,
            price=fill_price,
            notional=notional,
            fee=fee,
            timestamp=bar.timestamp,
            position_after=account.positions[bar.symbol],
            cash_after=account.cash,
            equity_after=account.equity,
        )


class PaperSession:
    """Closed-bar strategy/policy/paper-fill loop with restart-safe snapshots."""

    def __init__(
        self,
        program: StrategyProgram,
        *,
        config: PaperConfig | None = None,
        account: PaperAccount | None = None,
    ) -> None:
        self.program = program
        self.config = config or PaperConfig()
        self.account = account or PaperAccount.create(self.config.initial_cash)
        self.controller = PortfolioController(
            policy_id=f"paper:{program.strategy_id}",
            config=PortfolioPolicyConfig(
                max_position=self.config.max_position_fraction,
                max_gross_exposure=self.config.max_position_fraction,
                max_net_exposure=self.config.max_position_fraction,
                max_turnover=self.config.max_turnover,
                risk_budget_per_position=self.config.max_position_fraction,
                flat_on_abstain=True,
            ),
            support_roots=(program.program_sha256,),
        )
        self.engine = PaperExecutionEngine(self.config)
        self.history: list[MarketBar] = []
        self.processed_event_ids: set[str] = set()
        self.receipts: dict[str, dict[str, Any]] = {}
        self.entry_price: float | None = None
        self.bars_in_position = 0

    def _authority(self) -> Authority:
        return Authority(
            mode="shadow",
            objective_id="paper-trading-only",
            permission_generation="paper-v1",
            revocation_generation="paper-revocation-v1",
            venue_limits={"venue": self.config.venue, "external_effect": "none"},
        )

    def process_bar(self, bar: MarketBar) -> dict[str, Any]:
        event = bar.as_event(source_id=f"paper:{self.config.venue}", source_revision="closed-bar-v1")
        return self._process_canonical_bar(bar, event, data_health=None)

    def process_event(
        self,
        event: Event,
        *,
        data_health: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Process one admitted canonical bar without discarding its provenance."""

        if event.event_type != "market-bar":
            raise PaperTradingError("paper runtime accepts only canonical market-bar events")
        if data_health is not None:
            if data_health.get("state") != "GREEN" or data_health.get("can_open_exposure") is not True:
                raise PaperTradingError("canonical bar is blocked by data health")
        try:
            bar = MarketBar(**dict(event.payload))
        except (TypeError, ValueError) as exc:
            raise PaperTradingError("canonical market-bar payload is invalid") from exc
        if event.subject_ids != (bar.symbol,):
            raise PaperTradingError("canonical event subject does not match its market bar")
        if event.observed_at != bar.timestamp:
            raise PaperTradingError("canonical event observation time does not match its market bar")
        return self._process_canonical_bar(bar, event, data_health=data_health)

    def _process_canonical_bar(
        self,
        bar: MarketBar,
        event: Event,
        *,
        data_health: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        if self.history and bar.symbol != self.history[0].symbol:
            raise PaperTradingError("a paper session supports exactly one symbol")
        if event.event_id in self.processed_event_ids:
            return dict(self.receipts[event.event_id])
        if self.history and bar.timestamp <= self.history[-1].timestamp:
            raise PaperTradingError("paper bars must be strictly increasing")
        self.history.append(bar)
        self.history = self.history[-self.config.max_history :]
        self.account.mark(bar)
        position_fraction = self.account.exposure_fraction(bar.symbol, bar.close)
        position_state = (
            1
            if position_fraction > self.config.minimum_order_fraction
            else -1
            if position_fraction < -self.config.minimum_order_fraction
            else 0
        )
        features = _features(
            self.history,
            len(self.history) - 1,
            self.program,
            position=position_state,
            entry_price=self.entry_price,
            bars_in_position=self.bars_in_position,
        )
        direction = self.program.evaluate(features)
        volatility = max(abs(float(features.get("volatility", 0.0))), 1.0e-6)
        # Replay parity requires the policy layer to carry the discrete strategy
        # direction without changing it into a fractional risk score.
        signal = ProgramSignal(
            signal_id=f"{event.event_id}:signal",
            program_id=self.program.strategy_id,
            instrument=bar.symbol,
            regime_id="paper:closed-bar",
            direction=float(direction),
            expected_edge=volatility,
            expected_risk=volatility,
            applicability_status="evaluated",
            event_id=event.event_id,
            observation_id=f"{event.event_id}:observation",
            available_at=event.available_at,
            support_roots=(self.program.program_sha256,),
        )
        operation_id = f"paper:{self.config.venue}:{event.event_id}"
        decision = self.controller.decide(
            PortfolioState(equity=self.account.equity, positions={bar.symbol: position_fraction}),
            (signal,),
            authority=self._authority(),
            operation_id=operation_id,
        )
        target_exposure = float(decision["target_exposures"].get(bar.symbol, position_fraction))
        fill = self.engine.execute_target(
            self.account,
            bar,
            target_exposure=target_exposure,
            operation_id=operation_id,
            event_id=event.event_id,
        )
        new_fraction = self.account.exposure_fraction(bar.symbol, bar.close)
        if abs(new_fraction) < self.config.minimum_order_fraction:
            self.entry_price = None
            self.bars_in_position = 0
        elif fill is not None and (self.entry_price is None or fill.side == "buy" and new_fraction > position_fraction):
            self.entry_price = fill.price
            self.bars_in_position = 1
        elif abs(new_fraction) > self.config.minimum_order_fraction:
            self.bars_in_position += 1
        receipt: dict[str, Any] = {
            "schema": PAPER_BAR_RECEIPT_SCHEMA,
            "event": event.as_dict(),
            "signal": signal.as_dict(),
            "policy_decision": decision,
            "fill": fill.as_dict() if fill is not None else None,
            "account": self.account.as_dict(),
            "data_health": None if data_health is None else dict(data_health),
            "paper_only": True,
            "external_effect": "none",
        }
        receipt["content_sha256"] = digest_value(receipt)
        self.processed_event_ids.add(event.event_id)
        self.receipts[event.event_id] = receipt
        return dict(receipt)

    def snapshot(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": PAPER_SCHEMA,
            "config": self.config.as_dict(),
            "program": self.program.document(),
            "program_sha256": self.program.program_sha256,
            "account": self.account.as_dict(),
            "history": [bar.as_dict() for bar in self.history],
            "processed_event_ids": sorted(self.processed_event_ids),
            "receipts": list(self.receipts.values())[-self.config.max_history :],
            "entry_price": self.entry_price,
            "bars_in_position": self.bars_in_position,
            "paper_only": True,
        }
        body["content_sha256"] = digest_value(body)
        return body

    def save_state(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(self.snapshot(), ensure_ascii=False, sort_keys=True, indent=2) + "\n"
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
            handle.write(payload)
            temporary = Path(handle.name)
        os.replace(temporary, path)

    @classmethod
    def load_state(cls, path: Path, program: StrategyProgram) -> "PaperSession":
        value = json.loads(Path(path).read_text(encoding="utf-8"))
        if value.get("schema") != PAPER_SCHEMA or value.get("paper_only") is not True:
            raise PaperTradingError("paper state schema or mode mismatch")
        if value.get("program_sha256") != program.program_sha256:
            raise PaperTradingError("paper state belongs to a different strategy program")
        config = PaperConfig(**value["config"])
        session = cls(program, config=config, account=PaperAccount.from_dict(value["account"]))
        session.history = [MarketBar(**row) for row in value.get("history", [])]
        session.processed_event_ids = set(str(item) for item in value.get("processed_event_ids", []))
        session.receipts = {str(row["event"]["event_id"]): row for row in value.get("receipts", [])}
        session.entry_price = value.get("entry_price")
        session.bars_in_position = int(value.get("bars_in_position", 0))
        return session


class CoinbaseClosedCandleSource:
    """Read-only public Coinbase candles, excluding the currently open candle."""

    def __init__(self, product: str, *, granularity: int = 3600, limit: int = 300) -> None:
        if not product or not isinstance(product, str):
            raise PaperTradingError("Coinbase product must be nonempty text")
        if granularity not in {60, 300, 900, 3600, 21600, 86400}:
            raise PaperTradingError("unsupported Coinbase candle granularity")
        self.product = product
        self.granularity = granularity
        self.limit = max(32, min(int(limit), 300))

    def fetch_closed(self) -> tuple[MarketBar, ...]:
        query = urllib.parse.urlencode({"granularity": self.granularity})
        url = f"https://api.exchange.coinbase.com/products/{urllib.parse.quote(self.product, safe='')}/candles?{query}"
        request = urllib.request.Request(url, headers={"User-Agent": "CassiTradingPaper/1.0"})
        with urllib.request.urlopen(request, timeout=30) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if not isinstance(payload, list):
            raise PaperTradingError("Coinbase candle response must be a list")
        cutoff = int(time.time()) // self.granularity * self.granularity
        rows: list[MarketBar] = []
        for row in payload[: self.limit]:
            if not isinstance(row, list) or len(row) < 6:
                continue
            timestamp, low, high, open_price, close, volume = row[:6]
            timestamp_int = int(timestamp)
            if timestamp_int >= cutoff:
                continue
            observed = datetime.fromtimestamp(timestamp_int, tz=timezone.utc).isoformat().replace("+00:00", "Z")
            rows.append(
                MarketBar(
                    timestamp=observed,
                    symbol=self.product,
                    open=float(open_price),
                    high=float(high),
                    low=float(low),
                    close=float(close),
                    volume=float(volume),
                )
            )
        rows.sort(key=lambda bar: bar.timestamp)
        return tuple(rows)


__all__ = [
    "CoinbaseClosedCandleSource",
    "PAPER_ACCOUNT_SCHEMA",
    "PAPER_BAR_RECEIPT_SCHEMA",
    "PAPER_SCHEMA",
    "PaperAccount",
    "PaperConfig",
    "PaperExecutionEngine",
    "PaperFill",
    "PaperSession",
    "PaperTradingError",
]
