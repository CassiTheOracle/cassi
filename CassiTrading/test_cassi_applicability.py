from __future__ import annotations

import unittest

from cassi_applicability import (
    ApplicabilityError,
    ProgramBinding,
    RegimeConditionedEvaluator,
    contexts_from_market_observations,
    program_from_contract_dict,
)
from cassi_program_synthesizer import ProgramSynthesizer
from cassi_skill_bundle import build_skill_bundle, skill_contracts_from_bundle
from cassi_trading_foundry import generate_demo_bars
from cassi_world_model import MarketWorldModel


class ApplicabilityTests(unittest.TestCase):
    def _program_and_contexts(self):
        events = tuple(
            bar.as_event(source_id="applicability-test", source_revision="bars-v1")
            for bar in generate_demo_bars(64)
        )
        world = MarketWorldModel()
        world.update(events)
        skills = skill_contracts_from_bundle(build_skill_bundle())
        synthesis = ProgramSynthesizer().synthesize([skills[1]], task_id="regime-binding")
        program = program_from_contract_dict(synthesis["selected"]["program"])
        contexts = contexts_from_market_observations(events, world.observations, config=world.config)
        return program, contexts

    def test_program_is_bound_to_coordinates_only_in_applicable_regimes(self) -> None:
        program, contexts = self._program_and_contexts()
        allowed = tuple(sorted({context.regime_id for context in contexts if context.regime_id != "regime:warming"}))
        binding = ProgramBinding(
            binding_id="p1-trend-binding",
            allowed_regimes=allowed,
            parameter_map={"value": "trend"},
            constants={},
        )
        receipt = RegimeConditionedEvaluator().evaluate(program, binding, contexts)
        self.assertGreater(receipt["evaluated_count"], 0)
        self.assertGreater(receipt["inapplicable_count"], 0)
        self.assertEqual(receipt["error_count"], 0)
        self.assertTrue(all(row["status"] == "evaluated" for row in receipt["rows"] if row["regime_id"] in allowed and row["regime_id"] != "regime:warming"))

    def test_regime_guard_can_abstain_completely(self) -> None:
        program, contexts = self._program_and_contexts()
        binding = ProgramBinding(
            binding_id="never-applicable",
            allowed_regimes=("regime:never-observed",),
            parameter_map={"value": "trend"},
            constants={},
        )
        receipt = RegimeConditionedEvaluator().evaluate(program, binding, contexts)
        self.assertEqual(receipt["evaluated_count"], 0)
        self.assertEqual(receipt["inapplicable_count"], len(contexts))

    def test_binding_requires_complete_typed_parameter_closure(self) -> None:
        program, contexts = self._program_and_contexts()
        binding = ProgramBinding(
            binding_id="missing-value",
            allowed_regimes=(contexts[-1].regime_id,),
            parameter_map={},
            constants={},
        )
        with self.assertRaises(ApplicabilityError):
            RegimeConditionedEvaluator().evaluate(program, binding, contexts)


if __name__ == "__main__":
    unittest.main(verbosity=2)
