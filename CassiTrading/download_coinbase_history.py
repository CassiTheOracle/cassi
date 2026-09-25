#!/usr/bin/env python3
"""Download bounded OHLCV history from the public Coinbase API."""

from __future__ import annotations

import argparse
import csv
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cassi_trading_foundry import MarketBar, digest_value


MAX_CANDLES_PER_REQUEST = 300


def _utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _fetch_window(product: str, granularity: int, start: datetime, end: datetime) -> list[list[float]]:
    query = urllib.parse.urlencode(
        {
            "granularity": granularity,
            "start": start.isoformat().replace("+00:00", "Z"),
            "end": end.isoformat().replace("+00:00", "Z"),
        }
    )
    url = f"https://api.exchange.coinbase.com/products/{urllib.parse.quote(product, safe='')}/candles?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "CassiTradingFoundry/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    if not isinstance(payload, list):
        raise RuntimeError(f"Coinbase returned a non-list response: {payload!r}")
    return payload


def download(product: str, start: datetime, end: datetime, granularity: int) -> tuple[MarketBar, ...]:
    if end <= start:
        raise ValueError("end must be after start")
    step = timedelta(seconds=granularity)
    start_epoch = int(start.timestamp())
    end_epoch = int(end.timestamp())
    cursor = start
    rows: dict[int, list[float]] = {}
    while cursor < end:
        window_end = min(end, cursor + step * MAX_CANDLES_PER_REQUEST)
        for row in _fetch_window(product, granularity, cursor, window_end):
            if not isinstance(row, list) or len(row) != 6:
                raise RuntimeError(f"Coinbase returned an invalid candle row: {row!r}")
            timestamp = int(row[0])
            if timestamp < start_epoch or timestamp >= end_epoch:
                continue
            rows[timestamp] = [float(value) for value in row[1:]]
        cursor = window_end
    bars: list[MarketBar] = []
    for timestamp in sorted(rows):
        low, high, opening, closing, volume = rows[timestamp]
        stamp = datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat().replace("+00:00", "Z")
        bars.append(
            MarketBar(
                timestamp=stamp,
                symbol=product,
                open=opening,
                high=high,
                low=low,
                close=closing,
                volume=volume,
            )
        )
    if len(bars) < 12:
        raise RuntimeError(f"Coinbase returned only {len(bars)} usable bars")
    return tuple(bars)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--product", default="BTC-USD")
    parser.add_argument("--start", required=True, help="UTC ISO timestamp, for example 2025-01-01T00:00:00Z")
    parser.add_argument("--end", required=True, help="UTC ISO timestamp, exclusive")
    parser.add_argument("--granularity", type=int, default=3600, choices=(60, 300, 900, 3600, 21600, 86400))
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    bars = download(args.product, _utc(args.start), _utc(args.end), args.granularity)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=("timestamp", "symbol", "open", "high", "low", "close", "volume"),
        )
        writer.writeheader()
        writer.writerows(bar.as_dict() for bar in bars)
    print(
        json.dumps(
            {
                "status": "PASS",
                "product": args.product,
                "granularity": args.granularity,
                "bars": len(bars),
                "start": bars[0].timestamp,
                "end": bars[-1].timestamp,
                "data_sha256": digest_value([bar.as_dict() for bar in bars]),
                "out": str(args.out),
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
