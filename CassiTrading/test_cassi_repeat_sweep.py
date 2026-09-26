from __future__ import annotations

import unittest

from cassi_market_scenarios import SCENARIO_PROFILES, generate_scenario_bars
from cassi_repeat_sweep import REPEAT_SWEEP_SCHEMA, run_promote_repeat_sweep


class PromoteRepeatSweepTests(unittest.TestCase):
    def _bars(self):
        assignments = {
            "JUMP": SCENARIO_PROFILES["positive_jump"],
            "TREND": SCENARIO_PROFILES["trend"],
            "REVERSAL": SCENARIO_PROFILES["reversal"],
            "VOLATILE": SCENARIO_PROFILES["volatile"],
        }
        return {
            instrument: generate_scenario_bars(352, symbol=instrument, profile=profile)
            for instrument, profile in assignments.items()
        }

    def test_repeat_count_is_recorded_and_controls_fire(self) -> None:
        receipt = run_promote_repeat_sweep(
            self._bars(),
            source_instrument="JUMP",
            target_instruments=("TREND", "REVERSAL", "VOLATILE"),
            source_windows=4,
            source_repeat_counts=(1, 2, 3, 4),
        )
        self.assertEqual(
            [row.get("status", "measured") for row in receipt["results"]],
            ["measured", "measured", "measured", "capacity_rejected"],
        )
        for row in receipt["results"][:3]:
            self.assertEqual(row["lesion_authority_count"], 0)
            self.assertEqual(row["supported_control_authority_count"], 9)
            self.assertEqual(len(row["source_pre_update_outcomes"]), 4)
    def test_repeat_count_is_bounded(self) -> None:
        with self.assertRaises(ValueError):
            run_promote_repeat_sweep(
                self._bars(),
                source_instrument="JUMP",
                target_instruments=("TREND",),
                source_repeat_counts=(1, 5),
            )


if __name__ == "__main__":
    unittest.main(verbosity=2)
