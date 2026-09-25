from __future__ import annotations

import copy
import unittest

from cassi_aggressive_residency import AggressiveResidencyConfig
from cassi_field_recurrence import (
    RecurrenceWindow,
    run_field_recurrence_program,
    verify_field_recurrence_program,
)
from cassi_temporal_promotion import TemporalPromotionConfig
from cassi_trading_foundry import AcquisitionProfile, RefinementField, StrategyProgram
from run_cassi_trading_benchmark import _bar_series


class FieldRecurrenceTests(unittest.TestCase):
    @staticmethod
    def _field() -> RefinementField:
        return RefinementField(
            profile=AcquisitionProfile(
                wave_width=2_048,
                energy_limit=512.0,
                component_limit=4.0,
            )
        )

    @staticmethod
    def _residency() -> AggressiveResidencyConfig:
        return AggressiveResidencyConfig(
            warmup_bars=36,
            decision_interval=4,
            lesson_interval=12,
            outcome_horizon=4,
            max_hold_bars=40,
            cooldown_bars=16,
            purposeful_replay_episodes=1,
            stress_episodes=1,
        )

    def test_recurrence_keeps_field_lineage_and_held_out_read_only(self) -> None:
        bars = _bar_series("mixed", count=360, symbol="RECURRENCE", phase_offset=0.31)
        windows = (
            RecurrenceWindow("first", bars[0].timestamp, bars=96),
            RecurrenceWindow("second", bars[120].timestamp, bars=96),
        )
        held_out = RecurrenceWindow("held-out", bars[240].timestamp, bars=72)
        initial = self._field().checkpoint_bytes()
        receipt, checkpoint, _ = run_field_recurrence_program(
            bars,
            initial_checkpoint=initial,
            program=StrategyProgram.seed(),
            recurrence_windows=windows,
            held_out=held_out,
            residency_config=self._residency(),
            promotion_config=TemporalPromotionConfig(
                initial_development_bars=96,
                evaluation_bars=72,
                minimum_objective_delta=0.0,
                maximum_drawdown_increase=0.25,
                minimum_trades=1,
            ),
        )
        verification = verify_field_recurrence_program(
            receipt,
            initial_checkpoint=initial,
            final_checkpoint=checkpoint,
        )

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(verification["stage_count"], 2)
        self.assertFalse(receipt["held_out"]["learning_enabled"])
        self.assertEqual(
            receipt["stages"][0]["field_after_sha256"],
            receipt["stages"][1]["field_before_sha256"],
        )
        self.assertGreater(
            receipt["held_out"]["source"]["start_index"],
            receipt["stages"][-1]["source"]["end_index_exclusive"] - 1,
        )

        tampered = copy.deepcopy(receipt)
        tampered["stages"][1]["field_before_sha256"] = "0" * 64
        with self.assertRaises(ValueError):
            verify_field_recurrence_program(
                tampered,
                initial_checkpoint=initial,
                final_checkpoint=checkpoint,
            )

    def test_recurrence_rejects_overlapping_windows(self) -> None:
        bars = _bar_series("mixed", count=240, symbol="RECURRENCE", phase_offset=0.31)
        with self.assertRaises(ValueError):
            run_field_recurrence_program(
                bars,
                initial_checkpoint=self._field().checkpoint_bytes(),
                program=StrategyProgram.seed(),
                recurrence_windows=(
                    RecurrenceWindow("first", bars[0].timestamp, bars=96),
                    RecurrenceWindow("overlap", bars[48].timestamp, bars=96),
                ),
                held_out=RecurrenceWindow("held-out", bars[168].timestamp, bars=48),
                residency_config=self._residency(),
                promotion_config=TemporalPromotionConfig(
                    initial_development_bars=96,
                    evaluation_bars=48,
                    minimum_objective_delta=0.0,
                    maximum_drawdown_increase=0.25,
                    minimum_trades=1,
                ),
            )


if __name__ == "__main__":
    unittest.main()
