from __future__ import annotations

import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_persistence_sweep import PERSISTENCE_SWEEP_SCHEMA, run_promote_persistence_sweep


class PromotePersistenceTests(unittest.TestCase):
    def test_positive_source_persistence_has_live_controls(self) -> None:
        assignments = {
            "JUMP": SCENARIO_PROFILES["positive_jump"],
            "TREND": SCENARIO_PROFILES["trend"],
            "REVERSAL": SCENARIO_PROFILES["reversal"],
            "VOLATILE": SCENARIO_PROFILES["volatile"],
        }
        bars = {
            instrument: generate_scenario_bars(352, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }
        receipt = run_promote_persistence_sweep(
            bars,
            source_instrument="JUMP",
            target_instruments=("TREND", "REVERSAL", "VOLATILE"),
            source_window_counts=(1, 2, 5),
        )
        self.assertEqual(receipt["schema"], PERSISTENCE_SWEEP_SCHEMA)
        self.assertEqual([row["source_windows"] for row in receipt["results"]], [1, 2, 5])
        self.assertEqual([row["native_authority_rate"] for row in receipt["results"]], [1.0, 0.0, 1.0])
        self.assertEqual([row["authority_horizon"] for row in receipt["results"]], [96, None, 96])
        for row in receipt["results"]:
            self.assertEqual(row["lesion_authority_count"], 0)
            self.assertEqual(row["lesion_authority_by_target_start"], {"32": 0, "64": 0, "96": 0})
            self.assertEqual(row["supported_control_authority_count"], 9)
        self.assertEqual(
            receipt["results"][2]["source_pre_update_outcomes"],
            [None, "promote", None, "reject", None],
        )
        self.assertEqual(
            len(receipt["results"][2]["source_state_trace"][0]["field_state_vector"]),
            len(receipt["results"][2]["source_state_trace"][-1]["field_state_vector"]),
        )
        self.assertEqual(
            receipt["results"][2]["source_lesson_outcomes"],
            ["promote", "reject", "reject", "promote", "promote"],
        )

    def test_persistence_rejects_unordered_or_overbound_windows(self) -> None:
        bars = {"JUMP": generate_scenario_bars(352, symbol="JUMP", profile=SCENARIO_PROFILES["positive_jump"]), "TREND": generate_scenario_bars(352, symbol="TREND", profile=SCENARIO_PROFILES["trend"])}
        with self.assertRaises(ValueError):
            run_promote_persistence_sweep(bars, source_instrument="JUMP", target_instruments=("TREND",), source_window_counts=(2, 1))
        with self.assertRaises(ValueError):
            run_promote_persistence_sweep(bars, source_instrument="JUMP", target_instruments=("TREND",), source_window_counts=(9,))


if __name__ == "__main__":
    unittest.main(verbosity=2)
