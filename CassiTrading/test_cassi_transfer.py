from __future__ import annotations

import csv
import tempfile
import unittest
from pathlib import Path

from cassi_market_sources import HistoricalSource, load_historical_sources
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig, TransferError
from cassi_trading_foundry import generate_demo_bars


class TransferMatrixTests(unittest.TestCase):
    def _bars(self):
        return {
            "BTCUSD": generate_demo_bars(128, symbol="BTCUSD"),
            "ETHUSD": generate_demo_bars(128, symbol="ETHUSD"),
        }

    def test_csv_dataset_preserves_source_manifest_in_transfer_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as raw:
            directory = Path(raw)
            paths: list[tuple[str, Path]] = []
            for symbol in ("BTCUSD", "ETHUSD"):
                path = directory / f"{symbol}.csv"
                with path.open("w", newline="", encoding="utf-8") as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=("timestamp", "open", "high", "low", "close", "volume"),
                    )
                    writer.writeheader()
                    for bar in generate_demo_bars(128, symbol=symbol):
                        row = bar.as_dict()
                        row.pop("symbol")
                        writer.writerow(row)
                paths.append((symbol, path))
            dataset = load_historical_sources(
                tuple(
                    HistoricalSource(f"csv:{symbol}", path, symbol, availability_lag_seconds=1)
                    for symbol, path in paths
                )
            )
        receipt = CrossInstrumentTransferCampaign(
            TransferConfig(source_windows=1, target_start=64, target_windows=1)
        ).run_dataset(dataset)
        self.assertEqual(receipt["source_manifest"]["schema"], "cassi.market-source-manifest.v1")
        self.assertEqual(receipt["source_manifest"]["content_sha256"], dataset.content_sha256)
        for cell in receipt["cells"]:
            for row in cell["trained_target"] + cell["baseline_target"]:
                self.assertLess(row["decision_available_at"], row["outcome_observed_at"])

    def test_transfer_matrix_has_matched_cells_and_frozen_target_arms(self) -> None:
        receipt = CrossInstrumentTransferCampaign(
            TransferConfig(source_windows=2, target_start=64, target_windows=2)
        ).run(self._bars())
        self.assertEqual(receipt["instruments"], ["BTCUSD", "ETHUSD"])
        self.assertEqual(len(receipt["cells"]), 4)
        self.assertEqual(receipt["matched_source_starts"], [0, 8])
        self.assertEqual(receipt["matched_target_starts"], [64, 72])
        for cell in receipt["cells"]:
            self.assertTrue(cell["trained_target_field_stable"])
            self.assertTrue(cell["baseline_target_field_stable"])
            self.assertEqual(len(cell["source_field_sha256"]), 64)
            for row in cell["trained_target"] + cell["baseline_target"]:
                self.assertLess(row["decision_available_at"], row["outcome_observed_at"])
                self.assertNotIn(row["outcome_event_id"], row["prediction_input_event_ids"])
    def test_explicit_target_starts_span_multiple_regimes(self) -> None:
        config = TransferConfig(
            step_bars=32,
            source_windows=4,
            target_windows=1,
            target_starts=(32, 64, 96),
        )
        receipt = CrossInstrumentTransferCampaign(config).run(
            {
                "BTCUSD": generate_demo_bars(160, symbol="BTCUSD"),
                "ETHUSD": generate_demo_bars(160, symbol="ETHUSD"),
            }
        )
        self.assertEqual(receipt["matched_target_starts"], [32, 64, 96])
        self.assertEqual(receipt["config"]["target_starts"], [32, 64, 96])
        regimes = {
            row["regime_id"]
            for row in receipt["cells"][0]["trained_target"]
        }
        self.assertGreaterEqual(len(regimes), 2)
        self.assertTrue(receipt["cells"][0]["trained_target_field_stable"])

    def test_transfer_is_deterministic(self) -> None:
        config = TransferConfig(source_windows=1, target_start=64, target_windows=1)
        first = CrossInstrumentTransferCampaign(config).run(self._bars())
        second = CrossInstrumentTransferCampaign(config).run(self._bars())
        self.assertEqual(first, second)
        self.assertEqual(len(first["content_sha256"]), 64)

    def test_transfer_rejects_unmatched_source_lengths(self) -> None:
        bars = self._bars()
        bars["ETHUSD"] = bars["ETHUSD"][:-1]
        with self.assertRaises(TransferError):
            CrossInstrumentTransferCampaign(TransferConfig(source_windows=1, target_windows=1)).run(bars)


if __name__ == "__main__":
    unittest.main(verbosity=2)
