#!/usr/bin/env python3
"""Complete hourly gaps in an OHLCV history from a declared alternate source."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from cassi_trading_foundry import digest_value, load_bars_csv


SCHEMA = "cassi.trading.candle-completion.v1"
STEP_SECONDS = 3600


def _utc(value: str) -> datetime:
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _stamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _sha256(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def _fetch_bitstamp(start: datetime, end: datetime) -> list[dict[str, Any]]:
    query = urllib.parse.urlencode(
        {
            "step": STEP_SECONDS,
            "start": int(start.timestamp()),
            "end": int(end.timestamp()),
            "limit": 1000,
        }
    )
    url = f"https://www.bitstamp.net/api/v2/ohlc/btcusd/?{query}"
    request = urllib.request.Request(url, headers={"User-Agent": "CassiTradingFoundry/1.0"})
    with urllib.request.urlopen(request, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    rows = payload.get("data", {}).get("ohlc")
    if not isinstance(rows, list):
        raise RuntimeError(f"Bitstamp returned an invalid OHLC response: {payload!r}")
    return [row for row in rows if isinstance(row, dict)]


def _missing_ranges(bars: tuple[Any, ...]) -> list[tuple[datetime, datetime]]:
    gaps: list[tuple[datetime, datetime]] = []
    for earlier, later in zip(bars, bars[1:]):
        earlier_time = _utc(earlier.timestamp)
        later_time = _utc(later.timestamp)
        if later_time - earlier_time <= timedelta(hours=1):
            continue
        gaps.append((earlier_time + timedelta(hours=1), later_time))
    return gaps


def _row_from_bitstamp(row: dict[str, Any], timestamp: str) -> dict[str, Any]:
    return {
        "timestamp": timestamp,
        "symbol": "BTC-USD",
        "open": float(row["open"]),
        "high": float(row["high"]),
        "low": float(row["low"]),
        "close": float(row["close"]),
        "volume": float(row["volume"]),
        "source": "bitstamp_ohlc_gap_fill",
    }


def complete_history(input_path: Path, output_path: Path, receipt_path: Path) -> dict[str, Any]:
    input_path = Path(input_path)
    output_path = Path(output_path)
    receipt_path = Path(receipt_path)
    bars = load_bars_csv(input_path, symbol="BTC-USD")
    gaps = _missing_ranges(bars)
    by_timestamp: dict[str, dict[str, Any]] = {
        bar.timestamp: {**bar.as_dict(), "source": "coinbase_exchange_candles"}
        for bar in bars
    }
    filled: list[dict[str, Any]] = []
    for start, end in gaps:
        wanted: list[str] = []
        cursor = start
        while cursor < end:
            wanted.append(_stamp(cursor))
            cursor += timedelta(hours=1)
        wanted_epochs = {int(_utc(value).timestamp()): value for value in wanted}
        found: dict[str, dict[str, Any]] = {}
        for row in _fetch_bitstamp(start, end):
            try:
                timestamp = int(row["timestamp"])
                stamp = wanted_epochs.get(timestamp)
                if stamp is not None:
                    found[stamp] = _row_from_bitstamp(row, stamp)
            except (KeyError, TypeError, ValueError) as exc:
                raise RuntimeError(f"invalid Bitstamp candle row: {row!r}") from exc
        missing = [stamp for stamp in wanted if stamp not in found]
        if missing:
            raise RuntimeError(f"Bitstamp did not provide candles for {missing!r}")
        for stamp in wanted:
            by_timestamp[stamp] = found[stamp]
            filled.append(found[stamp])

    ordered = [by_timestamp[key] for key in sorted(by_timestamp)]
    for earlier, later in zip(ordered, ordered[1:]):
        delta = _utc(later["timestamp"]) - _utc(earlier["timestamp"])
        if delta != timedelta(hours=1):
            raise RuntimeError(
                f"completed history is not hourly at {earlier['timestamp']} -> {later['timestamp']}"
            )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["timestamp", "symbol", "open", "high", "low", "close", "volume", "source"],
        )
        writer.writeheader()
        writer.writerows(ordered)

    complete_bars = load_bars_csv(output_path, symbol="BTC-USD")
    body: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "PASS",
        "input": {
            "path": str(input_path),
            "file_sha256": _sha256(input_path.read_bytes()),
            "bars": len(bars),
            "first_timestamp": bars[0].timestamp,
            "last_timestamp": bars[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in bars]),
        },
        "completion": {
            "method": "alternate_exchange_gap_fill",
            "provider": "Bitstamp",
            "pair": "BTC/USD",
            "granularity_seconds": STEP_SECONDS,
            "gap_count_before": len(gaps),
            "filled_bars": len(filled),
            "filled": filled,
        },
        "output": {
            "path": str(output_path),
            "file_sha256": _sha256(output_path.read_bytes()),
            "bars": len(complete_bars),
            "first_timestamp": complete_bars[0].timestamp,
            "last_timestamp": complete_bars[-1].timestamp,
            "data_sha256": digest_value([bar.as_dict() for bar in complete_bars]),
            "source_counts": {
                source: sum(1 for row in ordered if row["source"] == source)
                for source in sorted({str(row["source"]) for row in ordered})
            },
        },
    }
    body["content_sha256"] = digest_value(body)
    receipt_path.parent.mkdir(parents=True, exist_ok=True)
    receipt_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return body


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(complete_history(args.input, args.output, args.receipt), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
