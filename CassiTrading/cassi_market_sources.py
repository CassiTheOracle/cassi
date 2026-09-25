"""Strict multi-source historical market ingestion and manifests."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence

from cassi_market_contracts import Event, canonical_bytes, digest_value
from cassi_trading_foundry import MarketBar, load_bars_csv


SOURCE_MANIFEST_SCHEMA = "cassi.market-source-manifest.v1"


class SourceError(ValueError):
    """A historical source violates its declared identity or chronology."""


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SourceError(f"{name} must be nonempty text")
    return value


@dataclass(frozen=True, slots=True)
class HistoricalSource:
    source_id: str
    path: Path
    symbol: str
    source_revision: str = "initial"
    availability_lag_seconds: int = 0

    def __post_init__(self) -> None:
        _text("source_id", self.source_id)
        if not isinstance(self.path, Path):
            raise SourceError("path must be a Path")
        _text("symbol", self.symbol)
        _text("source_revision", self.source_revision)
        if isinstance(self.availability_lag_seconds, bool) or not isinstance(self.availability_lag_seconds, int) or self.availability_lag_seconds < 0:
            raise SourceError("availability_lag_seconds must be a nonnegative integer")

    def as_dict(self, *, file_sha256: str, bar_count: int, event_root_sha256: str) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "path": str(self.path),
            "symbol": self.symbol,
            "source_revision": self.source_revision,
            "availability_lag_seconds": self.availability_lag_seconds,
            "file_sha256": file_sha256,
            "bar_count": bar_count,
            "event_root_sha256": event_root_sha256,
        }


def _shift_timestamp(timestamp: str, lag_seconds: int) -> str:
    raw = _text("timestamp", timestamp)
    synthetic = re.fullmatch(r"(\d{4}-\d{2}-\d{2})T(\d{4})Z", raw)
    if synthetic is not None:
        total_seconds = int(synthetic.group(2)) * 60 + lag_seconds
        minutes, seconds = divmod(total_seconds, 60)
        fractional = f".{seconds:02d}" if seconds else ""
        return f"{synthetic.group(1)}T{minutes:04d}{fractional}Z"
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SourceError(f"timestamp is not ISO-8601: {timestamp}") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    shifted = parsed.astimezone(timezone.utc) + timedelta(seconds=lag_seconds)
    return shifted.isoformat().replace("+00:00", "Z")


@dataclass(frozen=True, slots=True)
class HistoricalDataset:
    bars_by_instrument: Mapping[str, tuple[MarketBar, ...]]
    events_by_instrument: Mapping[str, tuple[Event, ...]]
    manifest: Mapping[str, Any]

    def __post_init__(self) -> None:
        if set(self.bars_by_instrument) != set(self.events_by_instrument):
            raise SourceError("bars and events must cover identical instruments")
        for instrument, bars in self.bars_by_instrument.items():
            events = self.events_by_instrument[instrument]
            if len(bars) != len(events):
                raise SourceError(f"bar/event count differs for {instrument}")
        canonical_bytes(dict(self.manifest))

    @property
    def content_sha256(self) -> str:
        return str(self.manifest["content_sha256"])


def load_historical_sources(sources: Sequence[HistoricalSource]) -> HistoricalDataset:
    if not sources:
        raise SourceError("at least one historical source is required")
    seen_ids: set[str] = set()
    seen_symbols: set[str] = set()
    bars_by_instrument: dict[str, tuple[MarketBar, ...]] = {}
    events_by_instrument: dict[str, tuple[Event, ...]] = {}
    manifest_sources: list[dict[str, Any]] = []
    for source in sources:
        if source.source_id in seen_ids:
            raise SourceError(f"duplicate source ID: {source.source_id}")
        if source.symbol in seen_symbols:
            raise SourceError(f"duplicate instrument source: {source.symbol}")
        if not source.path.exists() or not source.path.is_file():
            raise SourceError(f"historical source does not exist: {source.path}")
        seen_ids.add(source.source_id)
        seen_symbols.add(source.symbol)
        try:
            bars = load_bars_csv(source.path, symbol=source.symbol)
        except Exception as exc:
            raise SourceError(f"failed to load source {source.source_id}: {exc}") from exc
        if not bars:
            raise SourceError(f"source {source.source_id} contains no bars")
        events = tuple(
            bar.as_event(
                source_id=source.source_id,
                source_revision=source.source_revision,
                available_at=_shift_timestamp(bar.timestamp, source.availability_lag_seconds),
            )
            for bar in bars
        )
        available_times = [event.available_at for event in events]
        if available_times != sorted(available_times) or len(set(available_times)) != len(available_times):
            raise SourceError(f"source {source.source_id} has non-strict availability times")
        file_sha256 = hashlib.sha256(source.path.read_bytes()).hexdigest()
        event_root_sha256 = digest_value([event.as_dict() for event in events])
        bars_by_instrument[source.symbol] = tuple(bars)
        events_by_instrument[source.symbol] = events
        manifest_sources.append(
            source.as_dict(
                file_sha256=file_sha256,
                bar_count=len(bars),
                event_root_sha256=event_root_sha256,
            )
        )
    body: dict[str, Any] = {
        "schema": SOURCE_MANIFEST_SCHEMA,
        "sources": manifest_sources,
        "instruments": sorted(bars_by_instrument),
        "availability_policy": "event.available_at = observed_at + declared_lag",
    }
    body["content_sha256"] = digest_value(body)
    return HistoricalDataset(
        bars_by_instrument=bars_by_instrument,
        events_by_instrument=events_by_instrument,
        manifest=body,
    )


__all__ = ["HistoricalDataset", "HistoricalSource", "SOURCE_MANIFEST_SCHEMA", "SourceError", "load_historical_sources"]
