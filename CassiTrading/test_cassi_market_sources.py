from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from cassi_market_sources import HistoricalSource, SourceError, load_historical_sources
from cassi_trading_foundry import generate_demo_bars


class HistoricalSourceTests(unittest.TestCase):
    def _write_source(self, directory: Path, filename: str, symbol: str) -> Path:
        path = directory / filename
        bars = generate_demo_bars(32, symbol=symbol)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=("timestamp", "open", "high", "low", "close", "volume"))
            writer.writeheader()
            for bar in bars:
                row = bar.as_dict()
                row.pop("symbol")
                writer.writerow(row)
        return path

    def test_loader_preserves_each_source_and_declared_availability_lag(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            btc_path = self._write_source(directory, "btc.csv", "BTCUSD")
            eth_path = self._write_source(directory, "eth.csv", "ETHUSD")
            dataset = load_historical_sources(
                (
                    HistoricalSource("feed-btc", btc_path, "BTCUSD", availability_lag_seconds=30),
                    HistoricalSource("feed-eth", eth_path, "ETHUSD"),
                )
            )
        self.assertEqual(sorted(dataset.bars_by_instrument), ["BTCUSD", "ETHUSD"])
        btc_bar = dataset.bars_by_instrument["BTCUSD"][0]
        btc_event = dataset.events_by_instrument["BTCUSD"][0]
        self.assertEqual(btc_event.observed_at, btc_bar.timestamp)
        self.assertNotEqual(btc_event.available_at, btc_event.observed_at)
        self.assertEqual(dataset.manifest["schema"], "cassi.market-source-manifest.v1")
        self.assertEqual(dataset.content_sha256, dataset.manifest["content_sha256"])

    def test_loader_rejects_duplicate_instrument_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            first = self._write_source(directory, "first.csv", "BTCUSD")
            second = self._write_source(directory, "second.csv", "BTCUSD")
            with self.assertRaises(SourceError):
                load_historical_sources(
                    (
                        HistoricalSource("feed-a", first, "BTCUSD"),
                        HistoricalSource("feed-b", second, "BTCUSD"),
                    )
                )

    def test_loader_rejects_negative_availability_lag(self) -> None:
        with self.assertRaises(SourceError):
            HistoricalSource("feed", Path("bars.csv"), "BTCUSD", availability_lag_seconds=-1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
