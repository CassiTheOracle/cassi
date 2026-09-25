"""Adapters from chronological outcomes into the existing Cassi field owner."""

from __future__ import annotations

from typing import Mapping

from cassi_learning_loop import OutcomeLearner
from cassi_market_contracts import Outcome, Prediction
from cassi_trading_foundry import RefinementField, RefinementError


class FieldLearningAdapterError(ValueError):
    """The outcome cannot be mapped to an explicitly declared field lesson."""


class RefinementOutcomeLearner(OutcomeLearner):
    """Feed only explicitly mapped legacy refinements into ``RefinementField``.

    The mapping is deliberately supplied by the caller.  Unknown synthesized
    programs never fall through to an arbitrary mutation or a host-side guess.
    """

    def __init__(
        self,
        field: RefinementField,
        *,
        program_mutations: Mapping[str, str],
        repeats: int = 2,
    ) -> None:
        if not isinstance(field, RefinementField):
            raise FieldLearningAdapterError("field must be a RefinementField")
        if not program_mutations:
            raise FieldLearningAdapterError("program_mutations cannot be empty")
        if repeats < 1 or repeats > 4:
            raise FieldLearningAdapterError("repeats must be in [1, 4]")
        self.field = field
        self.program_mutations = dict(program_mutations)
        self.repeats = repeats

    @staticmethod
    def _signature(prediction: Prediction) -> str:
        signature = prediction.predicted_outcome.get("field_signature")
        if not isinstance(signature, str) or not signature.strip():
            raise FieldLearningAdapterError("prediction does not declare field_signature")
        return signature

    @staticmethod
    def _lesson_outcome(attribution: Mapping[str, object]) -> str:
        if attribution.get("status") != "resolved":
            return "uncertain"
        if attribution.get("risk_breach") is True:
            return "reject"
        if attribution.get("direction_correct") is False:
            return "reject"
        error = attribution.get("return_error")
        if isinstance(error, (int, float)) and error < 0.0:
            return "reject"
        if attribution.get("direction_correct") is True:
            return "promote"
        return "uncertain"

    def admit_outcome(
        self,
        prediction: Prediction,
        outcome: Outcome,
        attribution: Mapping[str, object],
    ) -> str:
        mutation = self.program_mutations.get(prediction.program_id)
        if mutation is None:
            raise FieldLearningAdapterError(
                f"program {prediction.program_id} has no explicit field mutation mapping"
            )
        signature = self._signature(prediction)
        lesson = self._lesson_outcome(attribution)
        try:
            self.field.learn(signature, mutation, lesson, repeats=self.repeats)
        except RefinementError as exc:
            raise FieldLearningAdapterError(str(exc)) from exc
        return self.field.fingerprint()

    def checkpoint_bytes(self) -> bytes:
        return self.field.checkpoint_bytes()

class NativeProgramOutcomeLearner(OutcomeLearner):
    """Represent arbitrary synthesized program IDs as native field actions."""

    def __init__(self, field: RefinementField, *, repeats: int = 2) -> None:
        if not isinstance(field, RefinementField):
            raise FieldLearningAdapterError("field must be a RefinementField")
        if repeats < 1 or repeats > 4:
            raise FieldLearningAdapterError("repeats must be in [1, 4]")
        self.field = field
        self.repeats = repeats

    def admit_outcome(
        self,
        prediction: Prediction,
        outcome: Outcome,
        attribution: Mapping[str, object],
    ) -> str:
        signature = RefinementOutcomeLearner._signature(prediction)
        lesson = RefinementOutcomeLearner._lesson_outcome(attribution)
        try:
            self.field.learn_program(
                signature,
                prediction.program_id,
                lesson,
                repeats=self.repeats,
            )
        except RefinementError as exc:
            raise FieldLearningAdapterError(str(exc)) from exc
        return self.field.fingerprint()

    def checkpoint_bytes(self) -> bytes:
        return self.field.checkpoint_bytes()


__all__ = ["FieldLearningAdapterError", "NativeProgramOutcomeLearner", "RefinementOutcomeLearner"]
