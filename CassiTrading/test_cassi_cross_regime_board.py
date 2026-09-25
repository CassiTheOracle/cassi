from __future__ import annotations

import copy
import unittest
from unittest.mock import patch
from dataclasses import replace

from cassi_aggressive_residency import AggressiveResidencyConfig
from cassi_cross_regime_board import (
    CONSTRUCTIVE_AUTHORITY_SCENARIOS,
    CrossRegimeScenario,
    parse_args,
    run_cross_regime_board,
    verify_cross_regime_board,
)
from cassi_temporal_promotion import TemporalPromotionConfig
from cassi_trading_foundry import AcquisitionProfile, RefinementField, StrategyProgram, digest_value
from run_cassi_trading_benchmark import _bar_series


class CrossRegimeBoardTests(unittest.TestCase):
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

    def _inputs(self):
        bars = _bar_series("mixed", count=420, symbol="CROSS-REGIME", phase_offset=0.44)
        scenarios = (
            CrossRegimeScenario(
                "first",
                bars[0].timestamp,
                "synthetic-up",
                development_bars=120,
                evaluation_bars=80,
            ),
            CrossRegimeScenario(
                "second",
                bars[160].timestamp,
                "synthetic-reversal",
                development_bars=120,
                evaluation_bars=80,
            ),
        )
        return bars, scenarios

    def test_constructive_authority_scenario_set_is_selectable(self) -> None:
        with patch(
            "sys.argv",
            [
                "cassi_cross_regime_board.py",
                "--history",
                "history.csv",
                "--initial-checkpoint",
                "initial.chk",
                "--program-receipt",
                "program.json",
                "--scenario-set",
                "constructive-authority",
                "--out",
                "out",
            ],
        ):
            args = parse_args()

        self.assertEqual(args.scenario_set, "constructive-authority")
        self.assertEqual(
            tuple(scenario.name for scenario in CONSTRUCTIVE_AUTHORITY_SCENARIOS),
            (
                "post-crash-expansion",
                "pre-etf-expansion",
                "post-etf-transition",
                "late-cycle-transition",
            ),
        )

    def test_board_keeps_fields_independent_and_receipt_verifiable(self) -> None:
        bars, scenarios = self._inputs()
        initial = self._field().checkpoint_bytes()
        board, artifacts = run_cross_regime_board(
            bars,
            initial_checkpoint=initial,
            program=StrategyProgram.seed(),
            scenarios=scenarios,
            residency_config=self._residency(),
            promotion_config=TemporalPromotionConfig(
                initial_development_bars=120,
                evaluation_bars=80,
                minimum_objective_delta=0.0,
                maximum_drawdown_increase=0.25,
                minimum_trades=1,
            ),
        )
        verification = verify_cross_regime_board(
            board,
            initial_checkpoint=initial,
            artifacts=artifacts,
        )

        self.assertEqual(verification["status"], "PASS")
        self.assertEqual(len(board["scenario_rows"]), 2)
        self.assertEqual(initial, self._field().restore(initial).checkpoint_bytes())
        for row in board["scenario_rows"]:
            self.assertGreater(row["source"]["evaluation"]["start_index"], 0)
            self.assertIn(
                row["classification"],
                {
                    "AUTHORITATIVE_TRANSFER",
                    "INHIBITORY_TRANSFER",
                    "ABSTENTION",
                    "HARMFUL_TRANSFER",
                    "NO_PORTABLE_AUTHORITY",
                },
            )

        tampered = copy.deepcopy(board)
        tampered["scenario_rows"][0]["deltas"]["net_return"] += 0.01
        tampered["content_sha256"] = digest_value(
            {key: value for key, value in tampered.items() if key != "content_sha256"}
        )
        with self.assertRaises(ValueError):
            verify_cross_regime_board(
                tampered,
                initial_checkpoint=initial,
                artifacts=artifacts,
            )

    def test_future_bars_outside_scenario_do_not_change_board(self) -> None:
        bars, scenarios = self._inputs()
        scenario = scenarios[0]
        initial = self._field().checkpoint_bytes()
        kwargs = {
            "initial_checkpoint": initial,
            "program": StrategyProgram.seed(),
            "scenarios": (scenario,),
            "residency_config": self._residency(),
            "promotion_config": TemporalPromotionConfig(
                initial_development_bars=120,
                evaluation_bars=80,
                minimum_objective_delta=0.0,
                maximum_drawdown_increase=0.25,
                minimum_trades=1,
            ),
        }
        original, _ = run_cross_regime_board(bars, **kwargs)
        mutated = tuple(
            replace(
                bar,
                close=bar.close * 1.7,
                high=max(bar.open, bar.close * 1.7) * 1.01,
                low=min(bar.open, bar.close * 1.7) * 0.99,
            )
            if index >= scenario.development_bars + scenario.evaluation_bars
            else bar
            for index, bar in enumerate(bars)
        )
        changed, _ = run_cross_regime_board(mutated, **kwargs)

        self.assertEqual(original["scenario_rows"], changed["scenario_rows"])
        self.assertEqual(original["verdict"], changed["verdict"])


if __name__ == "__main__":
    unittest.main()
