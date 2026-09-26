from __future__ import annotations

import unittest

from cassi_phase_generalization import PHASE_GENERALIZATION_SCHEMA, run_phase_generalization


class PhaseGeneralizationTests(unittest.TestCase):
    def test_phase_predictor_generalizes_with_exact_replay(self) -> None:
        receipt = run_phase_generalization(bar_count=352)
        self.assertEqual(receipt["schema"], PHASE_GENERALIZATION_SCHEMA)
        for case in receipt["cases"].values():
            matches = case["phase_receipt"]["matches"]
            self.assertTrue(all(row["exact_field_match"] for row in matches))
            self.assertTrue(all(row["prospective_matches_replay"] for row in matches))
            self.assertTrue(all(row["prospective_matches_native"] for row in matches))

    def test_reversal_source_has_negative_phase_without_false_promote(self) -> None:
        receipt = run_phase_generalization(bar_count=352)
        matches = receipt["cases"]["reversal"]["phase_receipt"]["matches"]
        self.assertEqual(matches[0]["source_lesson_outcomes"], ["reject"])
        self.assertEqual(matches[0]["prospective_readout"]["outcome"], "reject")
        self.assertEqual(matches[0]["native_authority_rate"], 0.0)
        volatile = receipt["cases"]["volatile"]["phase_receipt"]["matches"]
        self.assertEqual(volatile[0]["source_lesson_outcomes"], ["reject"])
        self.assertEqual(volatile[0]["native_authority_rate"], 0.0)
        self.assertTrue(receipt["mutation_control"]["predicted_authority_changed"])
        self.assertEqual(
            receipt["mutation_control"]["mutated_replay"]["readout"]["outcome"],
            "reject",
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
