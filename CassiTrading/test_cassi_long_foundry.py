from __future__ import annotations

import copy
import unittest

from cassi_long_foundry import run_long_foundry, verify_long_foundry_receipt
from cassi_trading_foundry import generate_demo_bars


class LongFoundryTests(unittest.TestCase):
    def test_chronological_windows_carry_program_and_field(self) -> None:
        receipt = run_long_foundry(
            generate_demo_bars(120),
            window_bars=40,
            step_bars=40,
            max_windows=3,
            max_rounds=2,
            max_candidates=4,
        )
        verification = verify_long_foundry_receipt(receipt)
        self.assertEqual(verification["window_count"], 3)
        self.assertTrue(receipt["field_changed"])
        self.assertEqual(
            receipt["windows"][1]["parent_program"]["program_sha256"],
            receipt["windows"][0]["selected_program"]["program_sha256"],
        )
        self.assertEqual(
            receipt["windows"][1]["field_before_sha256"],
            receipt["windows"][0]["field_after_sha256"],
        )
        quality = receipt["windows"][0]["field_quality"]
        self.assertGreater(quality["lesson_count"], 0)
        self.assertIn("admission_counts", quality)
        self.assertIn("generalized_count", quality)
        self.assertLessEqual(quality["generalized_count"], quality["lesson_count"])
        self.assertGreaterEqual(quality["candidate_count"], quality["lesson_count"])
        self.assertLessEqual(
            quality["distinct_signature_mutations"],
            quality["candidate_count"],
        )
        self.assertGreaterEqual(quality["repeats_total"], quality["lesson_count"])
        self.assertEqual(
            quality["validation_slice_evidence_count"],
            quality["candidate_count"] * 2,
        )
        self.assertLessEqual(quality["promoted_count"], quality["lesson_count"])

    def test_seed_mutation_is_bound_to_initial_program(self) -> None:
        receipt = run_long_foundry(
            generate_demo_bars(80),
            window_bars=40,
            step_bars=40,
            max_windows=1,
            max_rounds=1,
            max_candidates=2,
            seed_mutation="fast_down",
        )
        verification = verify_long_foundry_receipt(receipt)
        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(receipt["config"]["seed_mutation"], "fast_down")
        self.assertEqual(receipt["initial_program"]["mutation"], "fast_down")
        self.assertEqual(
            receipt["windows"][0]["parent_program"]["program_sha256"],
            receipt["initial_program"]["program_sha256"],
        )

    def test_timeframe_hours_scales_annualized_replay_metrics(self) -> None:
        bars = generate_demo_bars(80)
        hourly = run_long_foundry(
            bars,
            window_bars=40,
            step_bars=40,
            max_windows=1,
            max_rounds=1,
            max_candidates=2,
            timeframe_hours=1.0,
        )
        six_hour = run_long_foundry(
            bars,
            window_bars=40,
            step_bars=40,
            max_windows=1,
            max_rounds=1,
            max_candidates=2,
            timeframe_hours=6.0,
        )
        hourly_metrics = hourly["windows"][0]["holdout_metrics"]
        six_hour_metrics = six_hour["windows"][0]["holdout_metrics"]
        self.assertEqual(hourly["config"]["timeframe_hours"], 1.0)
        self.assertEqual(six_hour["config"]["timeframe_hours"], 6.0)
        self.assertEqual(six_hour_metrics["net_return"], hourly_metrics["net_return"])
        self.assertAlmostEqual(
            six_hour_metrics["sharpe"],
            hourly_metrics["sharpe"] / (6.0 ** 0.5),
        )

    def test_receipt_digest_rejects_mutation(self) -> None:
        receipt = run_long_foundry(
            generate_demo_bars(80),
            window_bars=40,
            step_bars=40,
            max_windows=1,
            max_rounds=1,
            max_candidates=2,
        )
        mutated = copy.deepcopy(receipt)
        mutated["windows"][0]["bars"] += 1
        with self.assertRaises(ValueError):
            verify_long_foundry_receipt(mutated)


if __name__ == "__main__":
    unittest.main(verbosity=2)
