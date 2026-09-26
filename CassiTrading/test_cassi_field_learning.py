from __future__ import annotations

import unittest

from cassi_field_learning import (
    FieldLearningAdapterError,
    NativeProgramOutcomeLearner,
    RefinementOutcomeLearner,
)
from cassi_learning_loop import ChronologicalLearningLoop, make_outcome
from cassi_market_contracts import Prediction
from cassi_trading_foundry import RefinementField


class FieldLearningAdapterTests(unittest.TestCase):
    def _prediction(self, program_id: str = "program-1") -> Prediction:
        return Prediction(
            prediction_id="prediction-1",
            predecessor_field_sha256="field-before",
            policy_id="policy-1",
            program_id=program_id,
            input_event_ids=("event-1",),
            available_at="2025-01-01T00:00:00Z",
            predicted_outcome={"return": 0.02, "field_signature": "edge"},
            alternatives=({"return": 0.0},),
            cost_expectation={"bps": 5.0},
            risk_expectation={"drawdown": 0.10},
        )

    def test_explicit_mapping_updates_real_refinement_field(self) -> None:
        field = RefinementField()
        before = field.fingerprint()
        prediction = self._prediction()
        learner = RefinementOutcomeLearner(
            field,
            program_mutations={"program-1": "entry_up"},
            repeats=1,
        )
        loop = ChronologicalLearningLoop(field_sha256="field-before", learner=learner)
        loop.issue_prediction(prediction)
        outcome = make_outcome(
            prediction,
            outcome_id="outcome-1",
            observed_at="2025-01-02T00:00:00Z",
            realized_outcome={"return": 0.03},
            execution_trace={"mode": "shadow"},
            cost_vector={"bps": 5.0},
            source_event_ids=("event-result",),
        )
        admitted = loop.settle_outcome(outcome)
        self.assertTrue(admitted["field_updated"])
        self.assertNotEqual(before, field.fingerprint())
        self.assertTrue(field.checkpoint_bytes())

    def test_unknown_program_never_falls_through_to_mutation(self) -> None:
        field = RefinementField()
        before = field.fingerprint()
        prediction = self._prediction("new-synthesized-program")
        learner = RefinementOutcomeLearner(
            field,
            program_mutations={"program-1": "entry_up"},
            repeats=1,
        )
        loop = ChronologicalLearningLoop(field_sha256="field-before", learner=learner)
        loop.issue_prediction(prediction)
        outcome = make_outcome(
            prediction,
            outcome_id="outcome-1",
            observed_at="2025-01-02T00:00:00Z",
            realized_outcome={"return": 0.03},
            execution_trace={},
            cost_vector={},
            source_event_ids=("event-result",),
        )
        with self.assertRaises(FieldLearningAdapterError):
            loop.settle_outcome(outcome)
        self.assertEqual(before, field.fingerprint())
        self.assertEqual(loop.pending[0].prediction_id, "prediction-1")

    def test_native_program_identity_updates_field_without_legacy_mapping(self) -> None:
        field = RefinementField()
        before = field.fingerprint()
        prediction = self._prediction("synth-unknown-program")
        learner = NativeProgramOutcomeLearner(field, repeats=1)
        loop = ChronologicalLearningLoop(field_sha256=before, learner=learner)
        prediction = type(prediction)(
            prediction_id=prediction.prediction_id,
            predecessor_field_sha256=before,
            policy_id=prediction.policy_id,
            program_id=prediction.program_id,
            input_event_ids=prediction.input_event_ids,
            available_at=prediction.available_at,
            predicted_outcome=prediction.predicted_outcome,
            alternatives=prediction.alternatives,
            cost_expectation=prediction.cost_expectation,
            risk_expectation=prediction.risk_expectation,
        )
        loop.issue_prediction(prediction)
        outcome = make_outcome(
            prediction,
            outcome_id="native-outcome",
            observed_at="2025-01-02T00:00:00Z",
            realized_outcome={"return": 0.03},
            execution_trace={},
            cost_vector={},
            source_event_ids=("native-event-result",),
        )
        admitted = loop.settle_outcome(outcome)
        self.assertTrue(admitted["field_updated"])
        self.assertNotEqual(before, field.fingerprint())


if __name__ == "__main__":
    unittest.main(verbosity=2)
