from __future__ import annotations

import unittest

from cassi_learning_loop import (
    ChronologicalLearningLoop,
    LearningLoopError,
    make_outcome,
)
from cassi_market_contracts import Prediction, digest_value


class RecordingLearner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, str, dict[str, object]]] = []

    def admit_outcome(self, prediction, outcome, attribution):
        if attribution.get("status") != "resolved":
            raise AssertionError("field update received unattributed outcome")
        self.calls.append((prediction.prediction_id, outcome.outcome_id, dict(attribution)))
        return digest_value({"prior": prediction.predecessor_field_sha256, "outcome": outcome.outcome_id})


class LearningLoopTests(unittest.TestCase):
    def _prediction(self, prediction_id: str, field_sha256: str, available_at: str) -> Prediction:
        return Prediction(
            prediction_id=prediction_id,
            predecessor_field_sha256=field_sha256,
            policy_id="policy-1",
            program_id="program-1",
            input_event_ids=(f"event-{prediction_id}",),
            available_at=available_at,
            predicted_outcome={"return": 0.02},
            alternatives=({"return": 0.0},),
            cost_expectation={"bps": 5.0},
            risk_expectation={"drawdown": 0.10},
        )

    def test_prediction_is_frozen_then_outcome_updates_field(self) -> None:
        learner = RecordingLearner()
        loop = ChronologicalLearningLoop(field_sha256="field-0", learner=learner)
        prediction = self._prediction("p1", "field-0", "2025-01-01T00:00:00Z")
        issued = loop.issue_prediction(prediction)
        self.assertEqual(issued["pending_count"], 1)
        outcome = make_outcome(
            prediction,
            outcome_id="o1",
            observed_at="2025-01-02T00:00:00Z",
            realized_outcome={"return": 0.03, "drawdown": 0.04},
            execution_trace={"status": "shadow"},
            cost_vector={"bps": 6.0},
            source_event_ids=("event-result-1",),
        )
        admitted = loop.settle_outcome(outcome)
        self.assertTrue(admitted["field_updated"])
        self.assertEqual(len(learner.calls), 1)
        self.assertEqual(loop.pending, ())
        self.assertEqual(loop.settled[0].outcome_id, "o1")
        self.assertAlmostEqual(admitted["attribution"]["return_error"], 0.01)
        self.assertEqual(admitted["attribution"]["cost_error_bps"], 1.0)

    def test_attribution_mismatch_cannot_update_field(self) -> None:
        learner = RecordingLearner()
        loop = ChronologicalLearningLoop(field_sha256="field-0", learner=learner)
        prediction = self._prediction("p1", "field-0", "2025-01-01T00:00:00Z")
        loop.issue_prediction(prediction)
        valid = make_outcome(
            prediction,
            outcome_id="o1",
            observed_at="2025-01-02T00:00:00Z",
            realized_outcome={"return": 0.03},
            execution_trace={},
            cost_vector={"bps": 5.0},
            source_event_ids=("event-result-1",),
        )
        invalid = type(valid)(
            outcome_id=valid.outcome_id,
            prediction_id=valid.prediction_id,
            observed_at=valid.observed_at,
            realized_outcome=valid.realized_outcome,
            execution_trace=valid.execution_trace,
            attribution={"status": "forged"},
            cost_vector=valid.cost_vector,
            source_event_ids=valid.source_event_ids,
        )
        with self.assertRaises(LearningLoopError):
            loop.settle_outcome(invalid)
        self.assertEqual(len(learner.calls), 0)
        self.assertEqual(loop.field_sha256, "field-0")
        self.assertEqual(loop.pending[0].prediction_id, "p1")

    def test_outcome_must_follow_prediction_and_can_only_settle_once(self) -> None:
        loop = ChronologicalLearningLoop(field_sha256="field-0")
        prediction = self._prediction("p1", "field-0", "2025-01-02T00:00:00Z")
        loop.issue_prediction(prediction)
        before = make_outcome(
            prediction,
            outcome_id="o-before",
            observed_at="2025-01-01T00:00:00Z",
            realized_outcome={"return": 0.0},
            execution_trace={},
            cost_vector={},
            source_event_ids=("event-before",),
        )
        with self.assertRaises(LearningLoopError):
            loop.settle_outcome(before)
        valid = make_outcome(
            prediction,
            outcome_id="o1",
            observed_at="2025-01-03T00:00:00Z",
            realized_outcome={"return": 0.0},
            execution_trace={},
            cost_vector={},
            source_event_ids=("event-result",),
        )
        loop.settle_outcome(valid)
        with self.assertRaises(LearningLoopError):
            loop.settle_outcome(valid)

    def test_checkpoint_restore_preserves_boundary_and_pending_state(self) -> None:
        loop = ChronologicalLearningLoop(field_sha256="field-0")
        prediction = self._prediction("p1", "field-0", "2025-01-01T00:00:00Z")
        loop.issue_prediction(prediction)
        snapshot = loop.snapshot()
        restored = ChronologicalLearningLoop.restore(snapshot)
        self.assertEqual(restored.snapshot(), snapshot)
        next_prediction = self._prediction("p2", "field-0", "2025-01-02T00:00:00Z")
        restored.issue_prediction(next_prediction)
        outcome = make_outcome(
            prediction,
            outcome_id="o1",
            observed_at="2025-01-03T00:00:00Z",
            realized_outcome={"return": 0.01},
            execution_trace={},
            cost_vector={},
            source_event_ids=("event-result",),
        )
        restored.settle_outcome(outcome)
        self.assertEqual(restored.pending[0].prediction_id, "p2")
        corrupted = dict(snapshot)
        corrupted["field_sha256"] = "mutated"
        with self.assertRaises(LearningLoopError):
            ChronologicalLearningLoop.restore(corrupted)


if __name__ == "__main__":
    unittest.main(verbosity=2)
