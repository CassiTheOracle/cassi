from __future__ import annotations

import copy
import unittest

from cassi_aggressive_residency import (
    AggressiveResidencyConfig,
    _score_action,
    _temporal_epoch,
)
from cassi_temporal_promotion import (
    TemporalPromotionConfig,
    run_temporal_promotion_campaign,
    verify_temporal_promotion_campaign,
)
from cassi_trading_foundry import AcquisitionProfile, RefinementField, StrategyProgram
from run_cassi_trading_benchmark import _bar_series


class TemporalPromotionTests(unittest.TestCase):
    @staticmethod
    def _field() -> RefinementField:
        return RefinementField(
            profile=AcquisitionProfile(
                wave_width=2048,
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
            max_hold_bars=48,
            cooldown_bars=24,
            purposeful_replay_episodes=2,
            stress_episodes=2,
        )

    def test_temporal_epoch_and_field_contradiction_age_authority(self) -> None:
        self.assertNotEqual(
            _temporal_epoch("2026-01-01T00:00:00Z", 0, 90),
            _temporal_epoch("2026-07-01T00:00:00Z", 0, 90),
        )
        field = self._field()
        context = ("market:v2:era=e1:regime=h4=up:d1=up:vol=normal:volume=normal:position=flat",)
        action = "target:+0.50"

        field.learn_market_action(context, action, "promote", repeats=2)
        promoted = field.predict_market_action(context, action)
        field.learn_market_action(context, action, "reject", repeats=4)
        contradicted = field.predict_market_action(context, action)
        field.learn_market_action(context, action, "promote", repeats=4)
        reconfirmed = field.predict_market_action(context, action)

        self.assertEqual(promoted["outcome"], "promote")
        self.assertEqual(contradicted["outcome"], "reject")
        self.assertEqual(reconfirmed["outcome"], "promote")

    def test_compounded_objective_penalizes_crash_exposure(self) -> None:
        bars = _bar_series("reversal", count=96, symbol="TEMPORAL-RISK", phase_offset=0.3)
        config = self._residency()
        index = 60
        quarter = _score_action(
            bars,
            index,
            0.25,
            current_position=0.0,
            volatility=0.01,
            config=config,
        )
        full = _score_action(
            bars,
            index,
            1.0,
            current_position=0.0,
            volatility=0.01,
            config=config,
        )

        self.assertIn("compounded_log_growth", full)
        self.assertIn("path_max_drawdown", full)
        self.assertIn("downside_deviation", full)
        self.assertGreater(full["path_max_drawdown"], quarter["path_max_drawdown"])
        self.assertGreater(quarter["objective"], full["objective"])

    def test_campaign_uses_later_windows_and_persists_promoted_runtime(self) -> None:
        bars = _bar_series("mixed", count=420, symbol="TEMPORAL-CAMPAIGN", phase_offset=1.17)
        initial = self._field().checkpoint_bytes()
        receipt, checkpoint, runtime = run_temporal_promotion_campaign(
            bars,
            initial_checkpoint=initial,
            program=StrategyProgram.seed(),
            residency_config=self._residency(),
            promotion_config=TemporalPromotionConfig(
                initial_development_bars=180,
                evaluation_bars=80,
                minimum_objective_delta=0.0,
                maximum_drawdown_increase=0.25,
                minimum_trades=1,
            ),
        )
        verification = verify_temporal_promotion_campaign(
            receipt,
            checkpoint=checkpoint,
            runtime_state=runtime,
        )

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(len(receipt["cycles"]), 3)
        for previous, current in zip(receipt["cycles"], receipt["cycles"][1:]):
            if previous["decision"]["selection"] == "candidate":
                chosen = previous["candidate"]
            elif previous["decision"]["selection"] == "starting_field":
                chosen = previous["starting_field_control"]
            else:
                chosen = previous["incumbent"]
            self.assertEqual(
                chosen["account"]["final"],
                current["candidate"]["account"]["initial"],
            )
        self.assertEqual(runtime["account"], receipt["final_account"])
        self.assertEqual(
            runtime["field_checkpoint_sha256"],
            receipt["final_field"]["checkpoint_sha256"],
        )

        tampered = copy.deepcopy(receipt)
        tampered["cycles"][0]["decision"]["objective_delta"] += 0.01
        with self.assertRaises(ValueError):
            verify_temporal_promotion_campaign(
                tampered,
                checkpoint=checkpoint,
                runtime_state=runtime,
            )


if __name__ == "__main__":
    unittest.main()
