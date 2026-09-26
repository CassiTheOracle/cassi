"""Chronological prediction/outcome lifecycle with field update boundaries."""

from __future__ import annotations

import math
from typing import Any, Mapping, Protocol, Sequence

from cassi_market_contracts import Outcome, Prediction, canonical_bytes, digest_value


LEARNING_LOOP_SCHEMA = "cassi.market-learning-loop.v1"


class LearningLoopError(ValueError):
    """A prediction/outcome lifecycle transition is invalid."""


class OutcomeLearner(Protocol):
    """Field-owned update boundary called only after outcome attribution."""

    def admit_outcome(
        self,
        prediction: Prediction,
        outcome: Outcome,
        attribution: Mapping[str, Any],
    ) -> str:
        """Return the successor field digest or raise without mutating state."""
        ...


def _text(name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise LearningLoopError(f"{name} must be nonempty text")
    return value


def _finite(name: str, value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise LearningLoopError(f"{name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise LearningLoopError(f"{name} must be finite")
    return result


def _key(timestamp: str, identity: str) -> tuple[str, str]:
    return (_text("timestamp", timestamp), _text("identity", identity))


def _prediction_from_dict(value: Mapping[str, Any]) -> Prediction:
    try:
        return Prediction(
            prediction_id=str(value["prediction_id"]),
            predecessor_field_sha256=str(value["predecessor_field_sha256"]),
            policy_id=str(value["policy_id"]),
            program_id=str(value["program_id"]),
            input_event_ids=tuple(str(item) for item in value["input_event_ids"]),
            available_at=str(value["available_at"]),
            predicted_outcome=dict(value["predicted_outcome"]),
            alternatives=tuple(dict(item) for item in value["alternatives"]),
            cost_expectation=dict(value["cost_expectation"]),
            risk_expectation=dict(value["risk_expectation"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LearningLoopError("malformed prediction checkpoint") from exc


def _outcome_from_dict(value: Mapping[str, Any]) -> Outcome:
    try:
        return Outcome(
            outcome_id=str(value["outcome_id"]),
            prediction_id=str(value["prediction_id"]),
            observed_at=str(value["observed_at"]),
            realized_outcome=dict(value["realized_outcome"]),
            execution_trace=dict(value["execution_trace"]),
            attribution=dict(value["attribution"]),
            cost_vector=dict(value["cost_vector"]),
            source_event_ids=tuple(str(item) for item in value["source_event_ids"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise LearningLoopError("malformed outcome checkpoint") from exc


def attribute_prediction(prediction: Prediction, outcome: Outcome) -> dict[str, Any]:
    """Compute deterministic attribution from the frozen prediction and outcome."""
    predicted_return = prediction.predicted_outcome.get("return")
    realized_return = outcome.realized_outcome.get("return")
    attribution: dict[str, Any] = {
        "prediction_id": prediction.prediction_id,
        "outcome_id": outcome.outcome_id,
        "status": "unresolved",
    }
    if isinstance(predicted_return, (int, float)) and not isinstance(predicted_return, bool) and isinstance(realized_return, (int, float)) and not isinstance(realized_return, bool):
        expected = _finite("predicted return", predicted_return)
        realized = _finite("realized return", realized_return)
        attribution.update(
            {
                "status": "resolved",
                "predicted_return": expected,
                "realized_return": realized,
                "return_error": realized - expected,
                "absolute_return_error": abs(realized - expected),
                "direction_correct": (expected == 0.0 and realized == 0.0) or (expected * realized > 0.0),
            }
        )
    expected_cost = prediction.cost_expectation.get("bps")
    realized_cost = outcome.cost_vector.get("bps")
    if isinstance(expected_cost, (int, float)) and isinstance(realized_cost, (int, float)):
        attribution.update(
            {
                "expected_cost_bps": _finite("expected cost", expected_cost),
                "realized_cost_bps": _finite("realized cost", realized_cost),
                "cost_error_bps": _finite("realized cost", realized_cost) - _finite("expected cost", expected_cost),
            }
        )
    expected_risk = prediction.risk_expectation.get("drawdown")
    realized_risk = outcome.realized_outcome.get("drawdown")
    if isinstance(expected_risk, (int, float)) and isinstance(realized_risk, (int, float)):
        expected = _finite("expected drawdown", expected_risk)
        realized = _finite("realized drawdown", realized_risk)
        attribution.update(
            {
                "expected_drawdown": expected,
                "realized_drawdown": realized,
                "risk_breach": realized > expected,
            }
        )
    return attribution


def make_outcome(
    prediction: Prediction,
    *,
    outcome_id: str,
    observed_at: str,
    realized_outcome: Mapping[str, Any],
    execution_trace: Mapping[str, Any],
    cost_vector: Mapping[str, Any],
    source_event_ids: Sequence[str],
) -> Outcome:
    """Create an outcome whose attribution is derived from the frozen prediction."""
    provisional = Outcome(
        outcome_id=outcome_id,
        prediction_id=prediction.prediction_id,
        observed_at=observed_at,
        realized_outcome=dict(realized_outcome),
        execution_trace=dict(execution_trace),
        attribution={"status": "provisional"},
        cost_vector=dict(cost_vector),
        source_event_ids=tuple(source_event_ids),
    )
    return Outcome(
        outcome_id=provisional.outcome_id,
        prediction_id=provisional.prediction_id,
        observed_at=provisional.observed_at,
        realized_outcome=provisional.realized_outcome,
        execution_trace=provisional.execution_trace,
        attribution=attribute_prediction(prediction, provisional),
        cost_vector=provisional.cost_vector,
        source_event_ids=provisional.source_event_ids,
    )


class ChronologicalLearningLoop:
    """Freeze predictions, admit outcomes once, then update the field."""

    def __init__(self, *, field_sha256: str, learner: OutcomeLearner | None = None) -> None:
        self.field_sha256 = _text("field_sha256", field_sha256)
        self.learner = learner
        self._pending: dict[str, Prediction] = {}
        self._settled: dict[str, Outcome] = {}
        self._last_prediction_key: tuple[str, str] | None = None
        self._last_outcome_key: tuple[str, str] | None = None
        self._revision = 0

    @property
    def pending(self) -> tuple[Prediction, ...]:
        return tuple(self._pending.values())

    @property
    def settled(self) -> tuple[Outcome, ...]:
        return tuple(self._settled.values())

    def issue_prediction(self, prediction: Prediction) -> dict[str, Any]:
        if not isinstance(prediction, Prediction):
            raise LearningLoopError("prediction must be a Prediction contract")
        if prediction.prediction_id in self._pending or prediction.prediction_id in {outcome.prediction_id for outcome in self._settled.values()}:
            raise LearningLoopError("prediction ID has already been issued")
        if prediction.predecessor_field_sha256 != self.field_sha256:
            raise LearningLoopError("prediction does not reference current field")
        prediction_key = _key(prediction.available_at, prediction.prediction_id)
        if self._last_prediction_key is not None and prediction_key <= self._last_prediction_key:
            raise LearningLoopError("predictions must advance chronologically")
        self._pending[prediction.prediction_id] = prediction
        self._last_prediction_key = prediction_key
        return {
            "schema": "cassi.prediction-issued.v1",
            "prediction_id": prediction.prediction_id,
            "prediction_sha256": prediction.content_sha256,
            "field_sha256": self.field_sha256,
            "pending_count": len(self._pending),
        }

    def settle_outcome(self, outcome: Outcome) -> dict[str, Any]:
        if not isinstance(outcome, Outcome):
            raise LearningLoopError("outcome must be an Outcome contract")
        prediction = self._pending.get(outcome.prediction_id)
        if prediction is None:
            if outcome.prediction_id in {row.prediction_id for row in self._settled.values()}:
                raise LearningLoopError("prediction outcome has already been admitted")
            raise LearningLoopError("outcome references no pending prediction")
        outcome_key = _key(outcome.observed_at, outcome.outcome_id)
        if outcome_key <= _key(prediction.available_at, prediction.prediction_id):
            raise LearningLoopError("outcome must occur after its prediction")
        if self._last_outcome_key is not None and outcome_key <= self._last_outcome_key:
            raise LearningLoopError("outcomes must advance chronologically")
        attribution = attribute_prediction(prediction, outcome)
        if dict(outcome.attribution) != attribution:
            raise LearningLoopError("outcome attribution does not match frozen prediction")
        predecessor_field_sha256 = self.field_sha256
        successor_field_sha256 = predecessor_field_sha256
        if self.learner is not None:
            successor_field_sha256 = _text(
                "successor field digest",
                self.learner.admit_outcome(prediction, outcome, attribution),
            )
        self._pending.pop(prediction.prediction_id)
        self._settled[outcome.outcome_id] = outcome
        self._last_outcome_key = outcome_key
        self.field_sha256 = successor_field_sha256
        self._revision += 1
        return {
            "schema": "cassi.outcome-admitted.v1",
            "prediction_id": prediction.prediction_id,
            "outcome_id": outcome.outcome_id,
            "attribution": attribution,
            "predecessor_field_sha256": predecessor_field_sha256,
            "successor_field_sha256": successor_field_sha256,
            "field_updated": successor_field_sha256 != predecessor_field_sha256,
            "revision": self._revision,
        }

    def snapshot(self) -> dict[str, Any]:
        body: dict[str, Any] = {
            "schema": LEARNING_LOOP_SCHEMA,
            "field_sha256": self.field_sha256,
            "revision": self._revision,
            "last_prediction_key": list(self._last_prediction_key) if self._last_prediction_key is not None else None,
            "last_outcome_key": list(self._last_outcome_key) if self._last_outcome_key is not None else None,
            "pending": [prediction.as_dict() for prediction in self._pending.values()],
            "settled": [outcome.as_dict() for outcome in self._settled.values()],
        }
        body["content_sha256"] = digest_value(body)
        return body

    def checkpoint_bytes(self) -> bytes:
        return canonical_bytes(self.snapshot())

    @classmethod
    def restore(cls, snapshot: Mapping[str, Any], *, learner: OutcomeLearner | None = None) -> "ChronologicalLearningLoop":
        if not isinstance(snapshot, Mapping):
            raise LearningLoopError("learning-loop snapshot must be an object")
        body = dict(snapshot)
        declared = body.pop("content_sha256", None)
        if declared != digest_value(body):
            raise LearningLoopError("learning-loop snapshot digest mismatch")
        if body.get("schema") != LEARNING_LOOP_SCHEMA:
            raise LearningLoopError("unknown learning-loop snapshot schema")
        loop = cls(field_sha256=str(body["field_sha256"]), learner=learner)
        loop._revision = int(body["revision"])
        for value in body.get("pending", []):
            prediction = _prediction_from_dict(value)
            loop._pending[prediction.prediction_id] = prediction
        for value in body.get("settled", []):
            outcome = _outcome_from_dict(value)
            loop._settled[outcome.outcome_id] = outcome
        prediction_key = body.get("last_prediction_key")
        outcome_key = body.get("last_outcome_key")
        if prediction_key is not None:
            loop._last_prediction_key = (str(prediction_key[0]), str(prediction_key[1]))
        if outcome_key is not None:
            loop._last_outcome_key = (str(outcome_key[0]), str(outcome_key[1]))
        return loop


__all__ = [
    "ChronologicalLearningLoop",
    "LEARNING_LOOP_SCHEMA",
    "LearningLoopError",
    "OutcomeLearner",
    "attribute_prediction",
    "make_outcome",
]
