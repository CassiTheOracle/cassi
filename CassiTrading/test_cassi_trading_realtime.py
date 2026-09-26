from __future__ import annotations

import unittest
from dataclasses import replace
from run_cassi_trading_realtime import (
    RealtimeConfig,
    run_historical_external_validation,
    run_realtime_benchmark,
    standard_scenario_bars,
    verify_historical_external_validation,
    verify_realtime_benchmark,
)


class RealtimeTradingBenchmarkTests(unittest.TestCase):
    def test_standard_stream_is_causal_and_field_adaptive(self) -> None:
        config = RealtimeConfig(
            bars=144,
            warmup_bars=24,
            adaptation_interval=24,
            max_candidates=3,
        )
        receipt = run_realtime_benchmark(config=config)
        verification = verify_realtime_benchmark(receipt)

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["decisions"], 143)
        self.assertGreaterEqual(verification["adaptations"], 3)
        self.assertNotEqual(receipt["field"]["before_sha256"], receipt["field"]["after_sha256"])
        self.assertGreater(receipt["stream"]["metrics"]["active_steps"], 0.0)
        self.assertTrue(
            any(event["selected_mutation"] is not None for event in receipt["adaptations"])
        )
        self.assertTrue(
            all(
                decision["available_prefix_count"] == decision["bar_index"] + 1
                for decision in receipt["stream"]["decisions"]
            )
        )

    def test_future_bar_mutation_cannot_change_prior_adaptation(self) -> None:
        config = RealtimeConfig(
            bars=144,
            warmup_bars=24,
            adaptation_interval=24,
            max_candidates=3,
        )
        original = standard_scenario_bars(count=config.bars)
        mutated = tuple(
            replace(
                bar,
                close=bar.close * 1.5,
                high=max(bar.open, bar.close * 1.5) * 1.01,
                low=min(bar.open, bar.close * 1.5) * 0.99,
            )
            if index >= 100
            else bar
            for index, bar in enumerate(original)
        )
        baseline = run_realtime_benchmark(original, config=config)
        changed = run_realtime_benchmark(mutated, config=config)

        self.assertNotEqual(baseline["data"]["data_sha256"], changed["data"]["data_sha256"])
        for baseline_event, changed_event in zip(
            baseline["adaptations"][:3], changed["adaptations"][:3]
        ):
            self.assertEqual(
                baseline_event["selected_strategy"]["program_sha256"],
                changed_event["selected_strategy"]["program_sha256"],
            )
            self.assertEqual(
                baseline_event["financial_composition"]["composition_id"],
                changed_event["financial_composition"]["composition_id"],
            )
            self.assertEqual(
                baseline_event["field_after_sha256"],
                changed_event["field_after_sha256"],
            )
        for baseline_decision, changed_decision in zip(
            baseline["stream"]["decisions"][:99], changed["stream"]["decisions"][:99]
        ):
            self.assertEqual(baseline_decision, changed_decision)

    def test_historical_windows_inherit_synthetic_calibration(self) -> None:
        config = RealtimeConfig(
            bars=96,
            warmup_bars=16,
            adaptation_interval=16,
            max_candidates=2,
        )
        receipt = run_historical_external_validation(
            standard_scenario_bars(count=192),
            config=config,
            max_windows=2,
        )
        verification = verify_historical_external_validation(receipt)

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(len(verification["windows"]), 2)
        calibration_program = receipt["protocol"]["calibration_program_sha256"]
        self.assertTrue(
            all(
                window["receipt"]["protocol"]["initial_field_mode"] == "inherited"
                and window["receipt"]["initial_strategy"]["program_sha256"] == calibration_program
                for window in receipt["windows"]
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
