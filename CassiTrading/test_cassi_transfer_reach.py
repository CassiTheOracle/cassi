from __future__ import annotations

import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, build_scenario_manifest, generate_scenario_bars
from cassi_transfer import TransferConfig
from cassi_transfer_reach import TRANSFER_REACH_SCHEMA, run_transfer_reach_matrix


class TransferReachTests(unittest.TestCase):
    def test_policy_arms_are_matched_and_field_stable(self) -> None:
        assignments = {
            "TREND": SCENARIO_PROFILES["trend"],
            "REVERSAL": SCENARIO_PROFILES["reversal"],
            "VOLATILE": SCENARIO_PROFILES["volatile"],
        }
        bars = {
            instrument: generate_scenario_bars(160, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }
        receipt = run_transfer_reach_matrix(
            bars,
            config=TransferConfig(step_bars=32, source_windows=4, target_starts=(32, 64, 96), target_windows=1),
            source_manifest=build_scenario_manifest(assignments, bar_count=160),
        )
        self.assertEqual(receipt["schema"], TRANSFER_REACH_SCHEMA)
        self.assertEqual(len(receipt["cells"]), 9)
        for cell in receipt["cells"]:
            self.assertEqual(set(cell["target_arms"]), {"native", "lesion", "supported-control"})
            self.assertEqual(cell["target_field_stable"], {
                "native": True,
                "lesion": True,
                "supported-control": True,
            })
            self.assertEqual(len(cell["target_arms"]["native"]), 3)
            self.assertEqual(len(cell["target_arms"]["lesion"]), 3)
            self.assertEqual(len(cell["target_arms"]["supported-control"]), 3)
            for row in cell["target_arms"]["supported-control"]:
                self.assertTrue(row["strict_promote_authority"])
                self.assertLess(row["decision_available_at"], row["outcome_observed_at"])
            for arm in ("native", "lesion"):
                for row in cell["target_arms"][arm]:
                    self.assertFalse(row["strict_promote_authority"])
                    self.assertEqual(row["direction"], 0.0)

    def test_native_and_control_have_distinct_policy_returns(self) -> None:
        bars = {
            "TREND": generate_scenario_bars(160, symbol="TREND", profile=SCENARIO_PROFILES["trend"]),
            "REVERSAL": generate_scenario_bars(160, symbol="REVERSAL", profile=SCENARIO_PROFILES["reversal"]),
        }
        receipt = run_transfer_reach_matrix(
            bars,
            config=TransferConfig(step_bars=32, source_windows=4, target_starts=(32,), target_windows=1),
        )
        for cell in receipt["cells"]:
            self.assertNotEqual(
                cell["mean_realized_return"]["native"],
                cell["mean_realized_return"]["supported-control"],
            )
            self.assertEqual(cell["mean_realized_return"]["native"], 0.0)


    def test_positive_jump_source_reaches_heterogeneous_targets(self) -> None:
        assignments = {
            "JUMP": SCENARIO_PROFILES["positive_jump"],
            "TREND": SCENARIO_PROFILES["trend"],
            "REVERSAL": SCENARIO_PROFILES["reversal"],
            "VOLATILE": SCENARIO_PROFILES["volatile"],
        }
        bars = {
            instrument: generate_scenario_bars(160, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }
        receipt = run_transfer_reach_matrix(
            bars,
            config=TransferConfig(step_bars=32, source_windows=1, target_starts=(32, 64, 96), target_windows=1),
            source_instruments=("JUMP",),
            target_instruments=("TREND", "REVERSAL", "VOLATILE"),
        )
        self.assertEqual(receipt["source_instruments"], ["JUMP"])
        self.assertEqual(receipt["target_instruments"], ["REVERSAL", "TREND", "VOLATILE"])
        self.assertEqual(len(receipt["cells"]), 3)
        for cell in receipt["cells"]:
            self.assertTrue(all(row["strict_promote_authority"] for row in cell["target_arms"]["native"]))
            self.assertTrue(all(not row["strict_promote_authority"] for row in cell["target_arms"]["lesion"]))
            self.assertNotEqual(
                cell["mean_realized_return"]["native"],
                cell["mean_realized_return"]["lesion"],
            )
if __name__ == "__main__":
    unittest.main(verbosity=2)
