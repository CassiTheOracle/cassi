from __future__ import annotations

import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_source_order_match import SOURCE_ORDER_MATCH_SCHEMA, run_source_order_match


class SourceOrderMatchTests(unittest.TestCase):
    def test_market_lesson_order_replays_exactly(self) -> None:
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
        receipt = run_source_order_match(
            bars,
            source_instrument="JUMP",
            target_instruments=("TREND", "REVERSAL", "VOLATILE"),
            source_window_counts=(1, 2, 3, 4, 5),
        )
        self.assertEqual(receipt["schema"], SOURCE_ORDER_MATCH_SCHEMA)
        self.assertTrue(all(row["exact_field_match"] for row in receipt["matches"]))
        self.assertTrue(all(row["prospective_matches_replay"] for row in receipt["matches"]))
        self.assertTrue(all(row["prospective_matches_native"] for row in receipt["matches"]))
        self.assertEqual(
            receipt["matches"][3]["source_lesson_outcomes"],
            ["promote", "reject", "reject", "promote"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
