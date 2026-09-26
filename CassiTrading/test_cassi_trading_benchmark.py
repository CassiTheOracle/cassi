from __future__ import annotations

import argparse
import csv
import tempfile
import unittest
from pathlib import Path

from cassi_trading_foundry import generate_demo_bars
from run_cassi_trading_benchmark import run_benchmark, verify_benchmark


class MilestoneBenchmarkTests(unittest.TestCase):
    def test_guided_and_blind_arms_are_matched_and_hash_bound(self) -> None:
        args = argparse.Namespace(
            max_rounds=1,
            max_candidates=4,
            fee_bps=10.0,
            slippage_bps=5.0,
        )
        receipt = run_benchmark(args)
        verification = verify_benchmark(receipt)
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(len(receipt["paired"]), len(receipt["scenarios"]))
        self.assertTrue(all(row["data_match"] for row in receipt["paired"]))
        self.assertTrue(all(row["fixed_data_match"] for row in receipt["paired"]))
        self.assertEqual(receipt["protocol"]["fixed_financial_composition"], "balanced")
        self.assertTrue(
            all(
                row["financial_composition_id"] == "balanced"
                and row["financial_composition_override"] == "balanced"
                for row in receipt["fixed"]
            )
        )
        self.assertTrue(
            all(
                isinstance(row["financial_composition_id"], str)
                and isinstance(row["financial_holdout_objective"], float)
                for row in receipt["guided"] + receipt["blind"]
            )
        )
        self.assertTrue(
            all(
                isinstance(row["guided_financial_holdout_objective"], float)
                and isinstance(row["blind_financial_holdout_objective"], float)
                for row in receipt["paired"]
            )
        )
        calibration = receipt["arm_protocol"]["guided"]["calibration"]
        self.assertEqual(calibration["outcome"], "promote")
        self.assertNotEqual(calibration["before_sha256"], calibration["after_sha256"])
        self.assertEqual(
            receipt["blind"][0]["field_before_sha256"],
            receipt["blind"][0]["field_after_sha256"],
        )
        mean_reversion_pair = receipt["paired"][2]
        self.assertTrue(mean_reversion_pair["program_changed"])
        self.assertGreater(mean_reversion_pair["guided_minus_blind_objective"], 0.0)

    def test_historical_csv_mode_uses_disjoint_calibration_and_windows(self) -> None:
        bars = generate_demo_bars(600, symbol="HIST")
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "historical.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=("timestamp", "symbol", "open", "high", "low", "close", "volume"),
                )
                writer.writeheader()
                writer.writerows(bar.as_dict() for bar in bars)
            args = argparse.Namespace(
                csv=path,
                symbol="HIST",
                max_rounds=1,
                max_candidates=4,
                fee_bps=10.0,
                slippage_bps=5.0,
            )
            receipt = run_benchmark(args)
        self.assertEqual(verify_benchmark(receipt)["status"], "PASS")
        self.assertEqual(receipt["protocol"]["input_source"], "historical_csv")
        self.assertEqual(receipt["protocol"]["source_bars"], 600)
        self.assertEqual(receipt["protocol"]["calibration_bars"], 100)
        self.assertEqual(receipt["protocol"]["evaluation_bars_per_scenario"], 100)
        self.assertTrue(all(row["data_match"] for row in receipt["paired"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
