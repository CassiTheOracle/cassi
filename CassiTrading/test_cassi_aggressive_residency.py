from __future__ import annotations

import copy
import unittest
from dataclasses import replace

from cassi_aggressive_residency import (
    AccountState,
    AggressiveResidencyConfig,
    _choose_target,
    _market_context,
    run_aggressive_curriculum,
    run_aggressive_stream,
    run_prospective,
    verify_aggressive_curriculum,
)
from cassi_trading_foundry import AcquisitionProfile, RefinementField, StrategyProgram
from run_cassi_trading_benchmark import _bar_series


class AggressiveResidencyTests(unittest.TestCase):
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
    def _config() -> AggressiveResidencyConfig:
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

    @staticmethod
    def _bars(count: int = 96):
        return _bar_series(
            "mixed",
            count=count,
            symbol="AGGRESSIVE-TEST",
            phase_offset=0.73,
        )

    def test_market_action_memory_reopens_with_supported_exact_recall(self) -> None:
        field = self._field()
        contexts = ("market:v1:h4=up:d1=up", "market:v1:d1=up:vol=normal:position=flat")
        receipt = field.learn_market_action(contexts, "target:+0.50", "promote", repeats=2)
        prediction = field.predict_market_action(contexts, "target:+0.50")
        restored = RefinementField.restore(field.checkpoint_bytes())

        self.assertNotEqual(receipt["field_before_sha256"], receipt["field_after_sha256"])
        self.assertEqual(prediction["status"], "supported")
        self.assertEqual(prediction["outcome"], "promote")
        self.assertEqual(restored.fingerprint(), field.fingerprint())
        self.assertEqual(
            restored.predict_market_action(contexts, "target:+0.50"),
            prediction,
        )

    def test_multiscale_context_is_causal_under_future_mutation(self) -> None:
        bars = self._bars(96)
        index = 48
        mutated = tuple(
            replace(
                bar,
                close=bar.close * 1.8,
                high=max(bar.open, bar.close * 1.8) * 1.01,
                low=min(bar.open, bar.close * 1.8) * 0.99,
            )
            if offset > index
            else bar
            for offset, bar in enumerate(bars)
        )
        fine = {
            bars[index].timestamp: {
                "return": 0.004,
                "volatility": 0.003,
                "volume": 12.0,
                "bars": 12.0,
            }
        }
        account = AccountState(equity=1.0, peak_equity=1.0, position=0.5)
        original_context = _market_context(
            bars,
            index,
            program=StrategyProgram.seed(),
            account=account,
            fine_context=fine,
        )
        mutated_context = _market_context(
            mutated,
            index,
            program=StrategyProgram.seed(),
            account=account,
            fine_context=fine,
        )

        self.assertEqual(original_context, mutated_context)
        self.assertIn("relation=regime", original_context["context_ids"][0])
        self.assertIn("d1=", original_context["context_ids"][0])
        self.assertIn("vol=", original_context["context_ids"][0])
        self.assertIn("era=e", original_context["context_ids"][0])
        self.assertEqual(len(original_context["relational_contexts"]), 11)
        self.assertIn("relation=transition:", original_context["context_ids"][2])
        self.assertIn("relation=acceleration:", original_context["context_ids"][3])
        self.assertIn("relation=opportunity:", original_context["context_ids"][4])
        self.assertIn("relation=mature-opportunity:", original_context["context_ids"][5])
        self.assertIn("d1=", original_context["features"]["transition"])
        self.assertIn("vol=", original_context["features"]["transition"])
        self.assertIn("coherence=", original_context["features"]["acceleration"])
        self.assertIn("vol=", original_context["features"]["acceleration"])
        self.assertIn("vol=", original_context["features"]["opportunity"])
        self.assertIn(
            original_context["features"]["mature_opportunity"].split(":", 1)[0],
            {"up", "down", "unresolved"},
        )
        self.assertEqual(original_context["features"]["position_bucket"], "long")

    def test_field_selects_fractional_size_and_account_carries_it(self) -> None:
        bars = self._bars()
        config = self._config()
        program = StrategyProgram.seed()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=program,
            account=account,
            fine_context={},
        )
        field = self._field()
        field.learn_market_action(
            context["learning_context_ids"],
            "target:+0.50",
            "promote",
            repeats=2,
        )
        selection = _choose_target(
            field,
            context["relational_contexts"],
            requested=1,
            account=account,
            config=config,
        )
        self.assertGreater(selection["target"], 0.25)
        self.assertLess(selection["target"], 0.5)
        self.assertEqual(selection["authority"], "field-graded-promote")
        self.assertGreater(selection["field_strength"], 0.0)
        self.assertLess(selection["field_strength"], 1.0)
        self.assertAlmostEqual(
            selection["target"],
            0.25 + selection["field_strength"] * 0.25,
        )

        _, stream, _ = run_aggressive_stream(
            bars,
            field=field,
            program=program,
            config=config,
            fine_context={},
            learning_enabled=False,
        )
        self.assertEqual(
            stream["decisions"][0]["authority"],
            "field-graded-promote",
        )
        self.assertGreater(stream["decisions"][0]["field_strength"], 0.0)
        self.assertLessEqual(abs(stream["account"]["final"]["position"]), 1.0)
        self.assertGreater(stream["account"]["metrics"]["trade_count"], 0.0)

    def test_relational_distance_continuously_grades_promotion_and_inhibition(self) -> None:
        bars = self._bars()
        config = self._config()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=StrategyProgram.seed(),
            account=account,
            fine_context={},
            config=config,
        )
        current = tuple(context["learning_contexts"])
        promoted = self._field()
        promoted.learn_market_action(
            context["learning_context_ids"],
            "target:+0.50",
            "promote",
            repeats=2,
        )

        direction_only = tuple(
            row
            if row["relation"] == "direction"
            else {**row, "context_id": f"{row['context_id']}:novel"}
            for row in current
        )
        directional = _choose_target(
            promoted,
            direction_only,
            requested=1,
            account=account,
            config=config,
        )
        exact = _choose_target(
            promoted,
            current,
            requested=1,
            account=account,
            config=config,
        )
        prior_era = tuple(
            {**row, "temporal_offset": 1, "proximity": row["proximity"] * 0.55}
            for row in current
        )
        prior = _choose_target(
            promoted,
            prior_era,
            requested=1,
            account=account,
            config=config,
        )

        self.assertEqual(directional["authority"], "field-graded-promote")
        self.assertGreater(exact["field_strength"], directional["field_strength"])
        self.assertGreater(directional["field_strength"], prior["field_strength"])
        self.assertGreater(exact["target"], directional["target"])
        self.assertGreater(directional["target"], prior["target"])
        self.assertAlmostEqual(
            directional["target"],
            0.25 + directional["field_strength"] * 0.25,
        )
        self.assertAlmostEqual(
            prior["target"],
            0.25 + prior["field_strength"] * 0.25,
        )
        inhibited = self._field()
        inhibited.learn_market_action(
            context["learning_context_ids"],
            "target:+0.25",
            "reject",
            repeats=2,
        )
        avoidance = _choose_target(
            inhibited,
            current,
            requested=1,
            account=account,
            config=config,
        )
        self.assertEqual(avoidance["authority"], "field-graded-avoidance")
        self.assertGreater(avoidance["field_strength"], 0.0)
        self.assertLess(avoidance["target"], 0.25)
        self.assertGreater(avoidance["target"], 0.0)
        self.assertAlmostEqual(
            avoidance["target"],
            0.25 * (1.0 - avoidance["field_strength"]),
        )

    def test_transition_relation_steers_without_full_regime_match(self) -> None:
        bars = self._bars()
        config = self._config()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=StrategyProgram.seed(),
            account=account,
            fine_context={},
            config=config,
        )
        transition = next(
            row for row in context["learning_contexts"] if row["relation"] == "transition"
        )
        field = self._field()
        field.learn_market_action(
            (transition["context_id"],),
            "target:+0.50",
            "promote",
            repeats=2,
        )
        selection = _choose_target(
            field,
            context["learning_contexts"],
            requested=1,
            account=account,
            config=config,
        )

        self.assertEqual(selection["authority"], "field-graded-promote")
        self.assertGreater(selection["field_strength"], 0.0)
        self.assertLessEqual(selection["field_strength"], transition["proximity"])
        self.assertGreater(selection["target"], 0.25)
        transition_row = next(
            row
            for row in selection["field_rows"]
            if row["target"] == 0.5
        )
        self.assertEqual(
            transition_row["prediction"]["relations"][0]["relation"],
            "regime",
        )
        self.assertEqual(
            next(
                row["relation"]
                for row in transition_row["prediction"]["relations"]
                if row["outcome"] == "promote"
            ),
            "transition",
        )

    def test_acceleration_relation_steers_without_transition_match(self) -> None:
        bars = self._bars()
        config = self._config()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=StrategyProgram.seed(),
            account=account,
            fine_context={},
            config=config,
        )
        acceleration = next(
            row
            for row in context["learning_contexts"]
            if row["relation"] == "acceleration"
        )
        field = self._field()
        field.learn_market_action(
            (acceleration["context_id"],),
            "target:+0.50",
            "promote",
            repeats=2,
        )
        selection = _choose_target(
            field,
            context["learning_contexts"],
            requested=1,
            account=account,
            config=config,
        )
        acceleration_row = next(
            row for row in selection["field_rows"] if row["target"] == 0.5
        )

        self.assertEqual(selection["authority"], "field-graded-promote")
        self.assertGreater(selection["field_strength"], 0.0)
        self.assertLessEqual(selection["field_strength"], acceleration["proximity"])
        self.assertGreater(selection["target"], 0.25)
        self.assertEqual(
            next(
                row["relation"]
                for row in acceleration_row["prediction"]["relations"]
                if row["outcome"] == "promote"
            ),
            "acceleration",
        )

    def test_opportunity_relation_carries_positive_authority_without_position_match(self) -> None:
        bars = self._bars()
        config = self._config()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=StrategyProgram.seed(),
            account=account,
            fine_context={},
            config=config,
        )
        opportunity = next(
            row
            for row in context["learning_contexts"]
            if row["relation"] == "opportunity"
        )
        self.assertNotIn("position=", opportunity["context_id"])
        field = self._field()
        field.learn_market_action(
            (opportunity["context_id"],),
            "target:+0.50",
            "promote",
            repeats=2,
        )
        selection = _choose_target(
            field,
            context["learning_contexts"],
            requested=1,
            account=account,
            config=config,
        )
        opportunity_row = next(
            row for row in selection["field_rows"] if row["target"] == 0.5
        )

        self.assertEqual(selection["authority"], "field-graded-promote")
        self.assertGreater(selection["target"], 0.25)
        self.assertLessEqual(selection["field_strength"], opportunity["proximity"])
        self.assertEqual(
            next(
                row["relation"]
                for row in opportunity_row["prediction"]["relations"]
                if row["outcome"] == "promote"
            ),
            "opportunity",
        )

    def test_mature_opportunity_relation_carries_position_independent_promotion(self) -> None:
        bars = self._bars()
        config = self._config()
        account = AccountState(equity=1.0, peak_equity=1.0)
        context = _market_context(
            bars,
            config.warmup_bars - 1,
            program=StrategyProgram.seed(),
            account=account,
            fine_context={},
            config=config,
        )
        mature = next(
            row
            for row in context["learning_contexts"]
            if row["relation"] == "mature-opportunity"
        )
        self.assertTrue(mature["context_id"].startswith("market:v5:"))
        self.assertNotIn("era=", mature["context_id"])
        self.assertNotIn("position=", mature["context_id"])

        field = self._field()
        field.learn_market_action(
            (mature["context_id"],),
            "target:+0.50",
            "promote",
            repeats=2,
        )
        selection = _choose_target(
            field,
            context["learning_contexts"],
            requested=1,
            account=account,
            config=config,
        )

        self.assertEqual(selection["authority"], "field-graded-promote")
        self.assertGreater(selection["target"], 0.25)
        mature_prediction = next(
            row["prediction"]
            for row in selection["field_rows"]
            if row["target"] == 0.5
        )
        self.assertEqual(
            next(
                relation["relation"]
                for relation in mature_prediction["relations"]
                if relation["outcome"] == "promote"
            ),
            "mature-opportunity",
        )

    def test_curriculum_changes_one_field_and_prospective_mode_is_read_only(self) -> None:
        bars = self._bars(100)
        config = self._config()
        initial = self._field().checkpoint_bytes()
        receipt, checkpoint, runtime_state = run_aggressive_curriculum(
            bars,
            initial_checkpoint=initial,
            program=StrategyProgram.seed(),
            config=config,
            fine_context={},
        )
        verification = verify_aggressive_curriculum(
            receipt,
            checkpoint=checkpoint,
            runtime_state=runtime_state,
        )

        self.assertEqual(verification["status"], "PASS")
        self.assertNotEqual(receipt["initial_field"]["field_sha256"], receipt["final_field"]["field_sha256"])
        self.assertGreater(len(receipt["streams"]["online_training"]["lessons"]), 0)
        self.assertGreaterEqual(receipt["purposeful_replay"]["failure_episode_count"], 1)
        self.assertGreaterEqual(receipt["purposeful_replay"]["stress_episode_count"], 1)
        self.assertFalse(receipt["streams"]["frozen_before"]["field"]["changed"])
        self.assertFalse(receipt["streams"]["frozen_after_diagnostic"]["field"]["changed"])

        before = bytes(checkpoint)
        prospective = run_prospective(
            bars,
            checkpoint=checkpoint,
            program=StrategyProgram.seed(),
            config=config,
        )
        self.assertEqual(checkpoint, before)
        self.assertFalse(prospective["learning_enabled"])
        self.assertEqual(prospective["checkpoint_sha256"], receipt["final_field"]["checkpoint_sha256"])

        tampered = copy.deepcopy(receipt)
        tampered["comparisons"]["frozen_after_vs_frozen_before"]["changed_targets"] += 1
        tampered["content_sha256"] = receipt["content_sha256"]
        with self.assertRaises(ValueError):
            verify_aggressive_curriculum(
                tampered,
                checkpoint=checkpoint,
                runtime_state=runtime_state,
            )


if __name__ == "__main__":
    unittest.main()
