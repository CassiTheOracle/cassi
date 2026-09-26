from __future__ import annotations

import unittest

from cassi_market_scenarios import (
    SCENARIO_MANIFEST_SCHEMA,
    SCENARIO_PROFILES,
    ScenarioError,
    build_scenario_manifest,
    generate_scenario_bars,
)
from cassi_transfer import CrossInstrumentTransferCampaign, TransferConfig


class ScenarioGeneratorTests(unittest.TestCase):
    def test_profiles_are_deterministic_and_distinct(self) -> None:
        trend_first = generate_scenario_bars(160, symbol="TREND", profile=SCENARIO_PROFILES["trend"])
        trend_second = generate_scenario_bars(160, symbol="TREND", profile=SCENARIO_PROFILES["trend"])
        volatile = generate_scenario_bars(160, symbol="VOLATILE", profile=SCENARIO_PROFILES["volatile"])
        self.assertEqual(trend_first, trend_second)
        self.assertNotEqual(
            tuple(bar.close for bar in trend_first),
            tuple(bar.close for bar in volatile),
        )
        self.assertNotEqual(
            tuple(bar.volume for bar in trend_first),
            tuple(bar.volume for bar in volatile),
        )

    def test_manifest_binds_each_instrument_to_profile(self) -> None:
        manifest = build_scenario_manifest(
            {"TREND": SCENARIO_PROFILES["trend"], "REVERSAL": SCENARIO_PROFILES["reversal"]},
            bar_count=160,
        )
        self.assertEqual(manifest["schema"], SCENARIO_MANIFEST_SCHEMA)
        self.assertEqual([row["instrument"] for row in manifest["instruments"]], ["REVERSAL", "TREND"])
        self.assertEqual(len(manifest["content_sha256"]), 64)

    def test_heterogeneous_transfer_preserves_frozen_target_controls(self) -> None:
        assignments = {
            "TREND": SCENARIO_PROFILES["trend"],
            "REVERSAL": SCENARIO_PROFILES["reversal"],
            "VOLATILE": SCENARIO_PROFILES["volatile"],
        }
        bars = {
            instrument: generate_scenario_bars(160, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }
        receipt = CrossInstrumentTransferCampaign(
            TransferConfig(step_bars=32, source_windows=4, target_starts=(32, 64, 96), target_windows=1)
        ).run(
            bars,
            source_manifest=build_scenario_manifest(assignments, bar_count=160),
        )
        self.assertEqual(len(receipt["cells"]), 9)
        self.assertEqual(receipt["source_manifest"]["schema"], SCENARIO_MANIFEST_SCHEMA)
        self.assertEqual(len(set(receipt["event_roots"].values())), 3)
        for cell in receipt["cells"]:
            self.assertTrue(cell["trained_target_field_stable"])
            self.assertTrue(cell["baseline_target_field_stable"])
            self.assertEqual(len(cell["trained_target"]), 3)

    def test_scenario_rejects_invalid_profile_and_short_market(self) -> None:
        with self.assertRaises(ScenarioError):
            generate_scenario_bars(31, profile=SCENARIO_PROFILES["trend"])
        with self.assertRaises(ScenarioError):
            build_scenario_manifest({}, bar_count=160)


if __name__ == "__main__":
    unittest.main(verbosity=2)
