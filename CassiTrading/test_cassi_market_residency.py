from __future__ import annotations

import copy
import unittest
from dataclasses import replace
from run_cassi_trading_benchmark import _bar_series
from run_cassi_market_residency import (
    ResidencyConfig,
    run_market_residency,
    run_market_residency_campaign,
    verify_market_residency,
    verify_market_residency_campaign,
)


class MarketResidencyTests(unittest.TestCase):
    @staticmethod
    def _config() -> ResidencyConfig:
        return ResidencyConfig(
            calibration_bars=144,
            external_bars=192,
            warmup_bars=24,
            review_interval=24,
        )

    def test_residency_is_causal_and_has_matched_transfer_arms(self) -> None:
        config = self._config()
        receipt = run_market_residency(config=config)
        verification = verify_market_residency(receipt)

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(
            len(receipt["calibration"]["stream"]["decisions"]),
            config.calibration_bars - 1,
        )
        self.assertEqual(
            len(receipt["external"]["static"]["stream"]["decisions"]),
            config.external_bars - 1,
        )
        self.assertNotEqual(
            receipt["calibration"]["field"]["before_sha256"],
            receipt["calibration"]["field"]["after_sha256"],
        )
        self.assertEqual(
            receipt["calibration"]["field"]["component_limit"],
            config.field_component_limit,
        )
        self.assertEqual(
            receipt["calibration"]["field"]["wave_width"],
            config.field_wave_width,
        )
        self.assertNotEqual(
            receipt["external"]["field_residency"]["field"]["before_sha256"],
            receipt["external"]["field_residency"]["field"]["after_sha256"],
        )
        self.assertTrue(
            any(
                review["next_mutation"] is not None
                for review in receipt["calibration"]["stream"]["reviews"]
            )
        )
        self.assertEqual(
            receipt["external"]["static"]["data"]["data_sha256"],
            receipt["external"]["field_residency"]["data"]["data_sha256"],
        )
        self.assertEqual(
            receipt["external"]["field_residency"]["initial_strategy"]["program_sha256"],
            receipt["calibration"]["stream"]["final_strategy"]["program_sha256"],
        )
        self.assertEqual(
            receipt["external"]["frozen_transfer"]["stream"]["final_strategy"]["program_sha256"],
            receipt["external"]["frozen_transfer"]["initial_strategy"]["program_sha256"],
        )
        self.assertTrue(
            all(
                row["available_prefix_count"] == row["bar_index"] + 1
                and row["future_bars_excluded"] == config.external_bars - row["bar_index"] - 2
                for row in receipt["external"]["field_residency"]["stream"]["decisions"]
            )
        )

    def test_capacity_events_are_recoverable_and_receipted(self) -> None:
        config = replace(self._config(), field_component_limit=0.5)
        receipt = run_market_residency(config=config)
        verification = verify_market_residency(receipt)
        self.assertEqual(verification["status"], "PASS")

        field = receipt["external"]["field_residency"]["field"]
        self.assertGreater(field["capacity_events"], 0)
        self.assertFalse(field["learning_saturated"])
        reviews = receipt["external"]["field_residency"]["stream"]["reviews"]
        capacity_reviews = [
            review
            for review in reviews
            if any(
                admission.get("admission") == "capacity-saturated"
                for admission in (
                    review["strategy_admission"],
                    review["mutation_admission"],
                    review["composition_admission"],
                )
            )
        ]
        self.assertTrue(capacity_reviews)
        self.assertTrue(
            all(
                admission["recoverable"]
                for review in capacity_reviews
                for admission in (
                    review["strategy_admission"],
                    review["mutation_admission"],
                    review["composition_admission"],
                )
                if admission.get("admission") == "capacity-saturated"
            )
        )
        first_capacity_review = min(
            review["review_index"] for review in capacity_reviews
        )
        self.assertTrue(
            any(
                review["review_index"] > first_capacity_review
                and review["field_before_sha256"] != review["field_after_sha256"]
                for review in reviews
            )
        )

    def test_future_bars_cannot_change_prior_external_reviews(self) -> None:
        config = self._config()
        original = _bar_series(
            "mixed",
            count=config.external_bars,
            symbol="RESIDENCY-EXTERNAL",
            phase_offset=1.73,
        )
        mutated = tuple(
            replace(
                bar,
                close=bar.close * 1.5,
                high=max(bar.open, bar.close * 1.5) * 1.01,
                low=min(bar.open, bar.close * 1.5) * 0.99,
            )
            if index >= 120
            else bar
            for index, bar in enumerate(original)
        )
        baseline = run_market_residency(config=config, external_bars=original)
        changed = run_market_residency(config=config, external_bars=mutated)

        self.assertNotEqual(
            baseline["external"]["data_sha256"], changed["external"]["data_sha256"]
        )
        for arm_name in ("static", "field_residency", "frozen_transfer"):
            baseline_arm = baseline["external"][arm_name]["stream"]
            changed_arm = changed["external"][arm_name]["stream"]
            self.assertEqual(baseline_arm["decisions"][:119], changed_arm["decisions"][:119])
            self.assertEqual(baseline_arm["reviews"][:4], changed_arm["reviews"][:4])

    def test_campaign_carries_field_and_separates_fresh_control(self) -> None:
        config = self._config()
        window_count = 3
        bars = _bar_series(
            "mixed",
            count=config.external_bars * window_count,
            symbol="RESIDENCY-CAMPAIGN",
            phase_offset=1.73,
        )
        receipt = run_market_residency_campaign(
            config=config,
            external_bars=bars,
            window_count=window_count,
        )
        verification = verify_market_residency_campaign(receipt)

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["windows"], window_count)
        calibration = receipt["calibration"]
        carried = receipt["arms"]["carried_field"]["windows"]
        frozen = receipt["arms"]["frozen_transfer"]["windows"]
        fresh = receipt["arms"]["fresh_field"]["windows"]
        static = receipt["arms"]["static_baseline"]["windows"]
        self.assertEqual(
            carried[0]["receipt"]["field"]["before_checkpoint_sha256"],
            calibration["field"]["checkpoint_sha256"],
        )
        self.assertEqual(
            carried[1]["receipt"]["field"]["before_checkpoint_sha256"],
            carried[0]["receipt"]["field"]["checkpoint_sha256"],
        )
        self.assertEqual(
            carried[1]["receipt"]["initial_strategy"]["program_sha256"],
            carried[0]["receipt"]["stream"]["final_strategy"]["program_sha256"],
        )
        self.assertTrue(
            all(
                row["receipt"]["initial_strategy"]["program_sha256"]
                == calibration["stream"]["final_strategy"]["program_sha256"]
                for row in frozen
            )
        )
        self.assertTrue(
            all(
                row["receipt"]["initial_strategy"]["program_sha256"]
                == fresh[0]["receipt"]["initial_strategy"]["program_sha256"]
                for row in fresh
            )
        )
        self.assertTrue(
            all(row["receipt"]["field"]["mode"] == "none" for row in static)
        )
        self.assertNotEqual(
            receipt["arms"]["carried_field"]["aggregate"]["compound_final_equity"],
            receipt["arms"]["static_baseline"]["aggregate"]["compound_final_equity"],
        )
        tampered = copy.deepcopy(receipt)
        tampered["arms"]["carried_field"]["windows"][1]["start_index"] += 1
        with self.assertRaises(ValueError):
            verify_market_residency_campaign(tampered)

    def test_verifier_rejects_receipt_mutation(self) -> None:
        receipt = run_market_residency(config=self._config())
        tampered = copy.deepcopy(receipt)
        tampered["pairs"]["guided_vs_static"]["net_return_delta"] += 1.0

        with self.assertRaises(ValueError):
            verify_market_residency(tampered)


if __name__ == "__main__":
    unittest.main(verbosity=2)
