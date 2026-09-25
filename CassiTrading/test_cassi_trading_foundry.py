from __future__ import annotations

import csv
import json
import tempfile
import unittest
from pathlib import Path

from cassi_trading_foundry import (
    FINANCIAL_COMPOSITIONS,
    FINANCIAL_ROLE_CONTRACTS,
    FoundryConfig,
    MarketBar,
    MarketDataError,
    RefinementField,
    ReplayConfig,
    STRATEGY_SOURCES,
    StrategyProgram,
    StrategyRefiner,
    TradingFoundryError,
    _child_program,
    digest_value,
    execute_financial_skill,
    financial_composition_candidates,
    generate_demo_bars,
    learn_financial_composition,
    load_bars_csv,
    run_backtest,
    run_foundry,
    score_financial_composition,
    select_financial_composition,
    teach_financial_math,
    verify_foundry_receipt,
)


class StrategyContractTests(unittest.TestCase):
    def test_seed_is_bounded_and_emits_a_position(self) -> None:
        strategy = StrategyProgram.seed()
        result = strategy.evaluate(
            {
                "ready": 1,
                "trend": 0.01,
                "momentum": 0.01,
                "volatility": 0.01,
                "trade_return": 0.0,
                "position": 0,
                "bars_in_position": 0,
            }
        )
        self.assertEqual(result, 1)
        self.assertEqual(len(strategy.program_sha256), 64)

    def test_strategy_family_catalog_is_bounded_and_reachable(self) -> None:
        features = {
            "ready": 1,
            "trend": 0.01,
            "momentum": 0.01,
            "volatility": 0.01,
            "trade_return": 0.0,
            "position": 0,
            "bars_in_position": 0,
        }
        expected_families = {
            "trend_pullback",
            "breakout",
            "mean_reversion",
            "trend_following",
            "momentum_continuation",
            "volatility_expansion",
            "range_reversion",
        }
        self.assertTrue(expected_families <= set(STRATEGY_SOURCES))
        seed = StrategyProgram.seed()
        for family in expected_families:
            program = StrategyProgram(
                strategy_id=f"contract-{family}",
                source=STRATEGY_SOURCES[family],
                parameters=seed.parameters,
                family=family,
            )
            self.assertIn(program.evaluate(features), {-1, 0, 1})
        for mutation in (
            "mean_reversion",
            "breakout",
            "trend_following",
            "momentum_continuation",
            "volatility_expansion",
            "range_reversion",
        ):
            self.assertEqual(_child_program(seed, mutation).family, mutation)
        self.assertTrue(
            {
                "trend_following",
                "momentum_continuation",
                "volatility_expansion",
                "range_reversion",
            }
            <= set(StrategyRefiner.MUTATIONS)
        )

    def test_replay_records_position_transition_and_cost(self) -> None:
        bars = generate_demo_bars(96)
        result = run_backtest(bars, StrategyProgram.seed(), ReplayConfig())
        self.assertGreater(len(result.decisions), 0)
        self.assertIn("cost_paid", result.metrics)
        self.assertTrue(all(row["position_before"] in {-1, 0, 1} for row in result.decisions))
        self.assertTrue(all(row["position_after"] in {-1, 0, 1} for row in result.decisions))


    def test_financial_compositions_execute_and_score(self) -> None:
        self.assertAlmostEqual(
            execute_financial_skill(
                "FM0",
                {"previous": 100.0, "current": 110.0},
            ),
            0.1,
        )
        bars = generate_demo_bars(96)
        result = run_backtest(bars, StrategyProgram.seed(), ReplayConfig())
        score = score_financial_composition(
            FINANCIAL_COMPOSITIONS["risk_first"],
            result.metrics,
            ReplayConfig(),
        )
        self.assertEqual(set(score), {
            "return_value",
            "risk_value",
            "execution_cost",
            "position_size_reference",
            "performance_value",
            "hit_rate",
            "objective",
            "objective_delta_vs_default",
        })
        self.assertTrue(all(isinstance(value, float) for value in score.values()))
        for composition_id in (
            "typed_balanced_risk_FM8",
            "typed_balanced_risk_FM9",
            "typed_balanced_risk_FM12",
            "typed_balanced_sizing_FM11",
            "typed_balanced_performance_FM10",
        ):
            deep_score = score_financial_composition(
                FINANCIAL_COMPOSITIONS[composition_id],
                result.metrics,
                ReplayConfig(),
            )
            self.assertTrue(all(isinstance(value, float) for value in deep_score.values()))
    def test_objective_reflects_performance_and_sizing_roles(self) -> None:
        bars = generate_demo_bars(96)
        metrics = run_backtest(bars, StrategyProgram.seed(), ReplayConfig()).metrics
        baseline = score_financial_composition(
            FINANCIAL_COMPOSITIONS["balanced"],
            metrics,
            ReplayConfig(),
        )
        profit_factor = score_financial_composition(
            FINANCIAL_COMPOSITIONS["typed_balanced_performance_FM10"],
            metrics,
            ReplayConfig(),
        )
        kelly_sizing = score_financial_composition(
            FINANCIAL_COMPOSITIONS["typed_balanced_sizing_FM11"],
            metrics,
            ReplayConfig(),
        )
        self.assertNotEqual(profit_factor["performance_value"], baseline["performance_value"])
        self.assertNotEqual(profit_factor["objective"], baseline["objective"])
        self.assertNotEqual(kelly_sizing["position_size_reference"], baseline["position_size_reference"])
        self.assertNotEqual(kelly_sizing["objective"], baseline["objective"])

    def test_field_selects_financial_composition_by_regime(self) -> None:
        field = RefinementField()
        teach_financial_math(field)
        selected = {
            signature: select_financial_composition(field, signature)["selected"]["composition_id"]
            for signature in ("drawdown", "cost", "edge", "flat", "stable")
        }
        self.assertEqual(selected["drawdown"], "risk_first")
        self.assertEqual(selected["cost"], "cost_aware")
        self.assertEqual(selected["edge"], "growth")
        self.assertEqual(selected["stable"], "balanced")
    def test_typed_grammar_generates_role_compatible_compositions(self) -> None:
        candidates = financial_composition_candidates("stable")
        self.assertGreater(len(candidates), len(("risk_first", "growth", "balanced")))
        self.assertTrue(all(candidate.composition_id.startswith(("typed_", "risk_", "growth", "balanced", "cost_")) for candidate in candidates))
        for candidate in candidates:
            self.assertIn(candidate.return_skill_id, FINANCIAL_ROLE_CONTRACTS["return"].skill_ids)
            self.assertIn(candidate.risk_skill_id, FINANCIAL_ROLE_CONTRACTS["risk"].skill_ids)
            self.assertEqual(candidate.cost_skill_id, "FM3")
            self.assertEqual(candidate.objective_skill_id, "FM5")

    def test_field_can_refine_a_typed_composition(self) -> None:
        field = RefinementField()
        typed = next(
            candidate
            for candidate in financial_composition_candidates("stable")
            if candidate.composition_id.startswith("typed_")
        )
        admission = learn_financial_composition(
            field,
            "stable",
            typed.composition_id,
            "promote",
        )
        selection = select_financial_composition(field, "stable")
        self.assertTrue(admission["promoted"])
        self.assertEqual(selection["selected"]["composition_id"], typed.composition_id)
        self.assertEqual(selection["selection_reason"], "field-supported-composition")


class FoundryTests(unittest.TestCase):
    def test_refinement_is_field_backed_and_holdout_is_evaluated(self) -> None:
        bars = generate_demo_bars(192)
        field = RefinementField()
        before = field.fingerprint()
        receipt = run_foundry(
            bars,
            field_memory=field,
            config=FoundryConfig(max_rounds=2, max_candidates_per_round=6),
        )
        self.assertEqual(receipt["status"], "PASS")
        self.assertEqual(receipt["field"]["before_sha256"], before)
        self.assertNotEqual(receipt["field"]["after_sha256"], before)
        self.assertEqual(receipt["field"]["qwen_calls"], 0)
        self.assertIn("metrics", receipt["holdout"])
        self.assertEqual(len(receipt["data"]["skill_ids"]), 21)
        self.assertEqual(receipt["data"]["financial_skill_ids"], [f"FM{index}" for index in range(13)])
        self.assertEqual(receipt["field"]["financial_teaching"]["status"], "PASS")
        self.assertIn(receipt["financial"]["composition"]["composition_id"], FINANCIAL_COMPOSITIONS)
        self.assertIn("objective", receipt["financial"]["validation"])
        self.assertIn("objective", receipt["financial"]["holdout"])
        self.assertTrue(
            all(
                "financial_composition" in round_receipt
                and all("financial_score" in candidate for candidate in round_receipt["candidates"])
                for round_receipt in receipt["development"]["rounds"]
            )
        )
        self.assertEqual(
            receipt["data"]["capability_bundle_sha256"],
            receipt["field"]["capability_bundle_sha256"],
        )
        self.assertEqual(
            receipt["data"]["skill_contract_sha256"],
            receipt["field"]["skill_contract_sha256"],
        )
        self.assertEqual(verify_foundry_receipt(receipt)["status"], "PASS")
        receipt = run_foundry(
            generate_demo_bars(192),
            field_memory=RefinementField(),
            config=FoundryConfig(max_rounds=1, max_candidates_per_round=2),
        )
        admissions = [
            candidate["field_admission"]
            for round_receipt in receipt["development"]["rounds"]
            for candidate in round_receipt["candidates"]
        ]
        self.assertTrue(admissions)
        self.assertTrue(all(isinstance(admission, dict) for admission in admissions))
        self.assertTrue(
            all(
                {"admission", "repeats", "promoted"}
                <= set(admission)
                for admission in admissions
            )
        )

    def test_financial_algorithms_are_written_into_field(self) -> None:
        field = RefinementField()
        before = field.fingerprint()
        teaching = teach_financial_math(field)
        self.assertEqual(teaching["status"], "PASS")
        self.assertEqual(teaching["algorithm_count"], 13)
        self.assertNotEqual(field.fingerprint(), before)
        self.assertEqual(
            [row["lesson_id"] for row in teaching["algorithms"]],
            [f"FM{index}" for index in range(13)],
        )
        self.assertTrue(all(row["differential"]["passed"] for row in teaching["algorithms"]))
        self.assertTrue(all(row["teaching"]["promoted"] for row in teaching["algorithms"]))
        self.assertTrue(all(row["prediction"]["status"] in {"supported", "unresolved"} for row in teaching["algorithms"]))
        self.assertGreaterEqual(
            sum(row["prediction"]["outcome"] == "promote" for row in teaching["algorithms"]),
            1,
        )

    def test_receipt_rejects_capability_closure_mutation(self) -> None:
        receipt = run_foundry(
            generate_demo_bars(192),
            field_memory=RefinementField(),
            config=FoundryConfig(max_rounds=2, max_candidates_per_round=6),
        )
        mutated = dict(receipt)
        mutated["data"] = dict(receipt["data"])
        mutated["data"]["capability_bundle_sha256"] = "stale-capability"
        body = dict(mutated)
        body.pop("content_sha256")
        mutated["content_sha256"] = digest_value(body)
        with self.assertRaises(TradingFoundryError):
            verify_foundry_receipt(mutated)

    def test_field_checkpoint_reopens_exactly(self) -> None:
        field = RefinementField()
        field.learn("edge", "entry_down", "promote")
        restored = RefinementField.restore(field.checkpoint_bytes())
        self.assertEqual(field.fingerprint(), restored.fingerprint())
        self.assertEqual(
            field.predict("edge", "entry_down")["outcome"],
            restored.predict("edge", "entry_down")["outcome"],
        )

    def test_field_quality_admission_reduces_redundancy(self) -> None:
        field = RefinementField()
        first = field.learn("edge", "entry_down", "promote", transfer_gate=True)
        confirmed = field.learn("edge", "entry_down", "promote", transfer_gate=True)
        uncertain = field.learn("stable", "entry_down", "uncertain", transfer_gate=True)

        self.assertEqual(first["admission"], "novel-provisional")
        self.assertEqual(first["repeats"], 2)
        self.assertFalse(first["promoted"])
        self.assertEqual(confirmed["admission"], "confirmed-reinforcement")
        self.assertEqual(confirmed["repeats"], 1)
        self.assertTrue(confirmed["promoted"])
        self.assertEqual(uncertain["admission"], "uncertain-provisional")
        self.assertEqual(uncertain["repeats"], 1)
        self.assertFalse(uncertain["promoted"])

    def test_transfer_gate_reproduces_on_held_out_context(self) -> None:
        field = RefinementField()
        provisional = field.learn_transfer_gated("drawdown", "entry_down", "promote")
        held_out_prediction = field.predict("cost", "entry_down")
        confirmation = field.learn_transfer_gated("cost", "entry_down", "promote")

        self.assertEqual(provisional["admission"], "novel-provisional")
        self.assertFalse(provisional["promoted"])
        self.assertEqual(held_out_prediction["context_scope"], "family")
        self.assertEqual(held_out_prediction["transfer_family"], "risk")
        self.assertEqual(held_out_prediction["outcome"], "promote")
        self.assertEqual(
            held_out_prediction["reason"],
            "field-supported-family-context",
        )
        self.assertEqual(confirmation["admission"], "confirmed-reinforcement")
        self.assertEqual(confirmation["prediction_context_scope"], "family")
        self.assertTrue(confirmation["promoted"])

    def test_transfer_gate_abstains_across_families(self) -> None:
        field = RefinementField()
        field.learn_transfer_gated("edge", "entry_down", "promote")
        prediction = field.predict("cost", "entry_down")

        self.assertIsNone(prediction["outcome"])
        self.assertEqual(prediction["context_scope"], "specific")
        self.assertNotEqual(prediction["reason"], "field-supported-family-context")

    def test_future_bar_mutation_does_not_change_prior_decision(self) -> None:
        bars = list(generate_demo_bars(96))
        baseline = run_backtest(bars, StrategyProgram.seed())
        changed = list(bars)
        last = changed[-1]
        changed[-1] = MarketBar(
            timestamp=last.timestamp,
            symbol=last.symbol,
            open=last.open,
            high=last.high * 2.0,
            low=last.low,
            close=last.close * 2.0,
            volume=last.volume,
        )
        altered = run_backtest(changed, StrategyProgram.seed())
        self.assertEqual(baseline.decisions[0], altered.decisions[0])


class CsvTests(unittest.TestCase):
    def test_csv_loader_preserves_order_and_rejects_unsorted_rows(self) -> None:
        bars = generate_demo_bars(32)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bars.csv"
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=("timestamp", "symbol", "open", "high", "low", "close", "volume"))
                writer.writeheader()
                for bar in bars:
                    writer.writerow(bar.as_dict())
            loaded = load_bars_csv(path, symbol="BTCUSDT")
            self.assertEqual([row.timestamp for row in loaded], [row.timestamp for row in bars])

            rows = [bar.as_dict() for bar in bars]
            rows[2], rows[3] = rows[3], rows[2]
            with path.open("w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=rows[0].keys())
                writer.writeheader()
                writer.writerows(rows)
            with self.assertRaises(MarketDataError):
                load_bars_csv(path, symbol="BTCUSDT")


if __name__ == "__main__":
    unittest.main(verbosity=2)
