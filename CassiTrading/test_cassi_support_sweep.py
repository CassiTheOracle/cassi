from __future__ import annotations

import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_support_sweep import SUPPORT_SWEEP_SCHEMA, run_support_sweep
from cassi_transfer import TransferConfig


class SupportSweepTests(unittest.TestCase):
    def test_sweep_is_chronological_and_bounded(self) -> None:
        bars = {
            "TREND": generate_scenario_bars(352, symbol="TREND", profile=SCENARIO_PROFILES["trend"]),
            "REVERSAL": generate_scenario_bars(352, symbol="REVERSAL", profile=SCENARIO_PROFILES["reversal"]),
        }
        receipt = run_support_sweep(
            bars,
            base_config=TransferConfig(step_bars=32, target_start=32, target_windows=1),
            max_source_windows=4,
        )
        self.assertEqual(receipt["schema"], SUPPORT_SWEEP_SCHEMA)
        self.assertEqual(receipt["max_source_windows"], 4)
        for rows in receipt["instruments"].values():
            self.assertEqual([row["source_windows"] for row in rows], [1, 2, 3, 4])
            self.assertEqual([row["source_starts"] for row in rows], [[0], [0, 32], [0, 32, 64], [0, 32, 64, 96]])
            self.assertTrue(all(row["field_before_sha256"] != row["field_after_sha256"] for row in rows))

    def test_sweep_rejects_unbounded_request(self) -> None:
        bars = {"TREND": generate_scenario_bars(352, symbol="TREND", profile=SCENARIO_PROFILES["trend"])}
        with self.assertRaises(ValueError):
            run_support_sweep(bars, max_source_windows=9)

    def test_positive_jump_can_acquire_native_promote(self) -> None:
        bars = {
            "JUMP": generate_scenario_bars(
                352,
                symbol="JUMP",
                profile=SCENARIO_PROFILES["positive_jump"],
            )
        }
        receipt = run_support_sweep(
            bars,
            base_config=TransferConfig(step_bars=32, target_start=32, target_windows=1),
            max_source_windows=1,
        )
        arm = receipt["instruments"]["JUMP"][0]
        self.assertTrue(arm["strict_promote_authority"])
        self.assertEqual(arm["readout"]["outcome"], "promote")


if __name__ == "__main__":
    unittest.main(verbosity=2)
