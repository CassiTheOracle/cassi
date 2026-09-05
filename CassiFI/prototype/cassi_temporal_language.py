"""Temporal prediction, ordering, and causal ports over the live Qi field."""
from __future__ import annotations

import dataclasses
import math
import struct
from collections.abc import Callable, Mapping

from cassi_field_language import (
    CassiQiTrajectoryLaw,
    QiFieldController,
    QiFieldState,
    qi_state_sha256,
)
from cassi_grounded_language import (
    CassiGroundedEventCodec,
    CassiGroundedLanguageError,
    GROUND_ACTIONS,
    GROUND_CAUSES,
    GROUND_CHANGES,
    GROUND_ORDER_POSITIONS,
    GROUND_TIME_TARGETS,
    sense_grounded_symbols,
)

TEMPORAL_DECISION_SCHEMA = "cassi.qi-temporal-decision.v1"
TEMPORAL_TRANSITION_SCHEMA = "cassi.qi-temporal-transition.v1"
TEMPORAL_TRANSITION_OFFSET = 9
TEMPORAL_ACTION_OFFSET = 13
TEMPORAL_ORDER_OFFSET = 18
TEMPORAL_VALID_OFFSET = 22
_TEMPORAL_CANDIDATES: Mapping[str, tuple[str, ...]] = {
    "prediction": GROUND_CHANGES,
    "observed-change": GROUND_CHANGES,
    "cause": GROUND_CAUSES,
    "time-target": GROUND_TIME_TARGETS,
    "order-position": GROUND_ORDER_POSITIONS,
}
_CHANGE_TEXT: Mapping[str, str] = {
    "change.x-decrease": "x to decrease",
    "change.x-increase": "x to increase",
    "change.y-increase": "y to increase",
    "change.y-decrease": "y to decrease",
    "change.none": "no position change",
}


@dataclasses.dataclass(frozen=True, slots=True)
class CassiTemporalTransition:
    before: tuple[float, float]
    after: tuple[float, float]
    action_id: str
    schema: str = TEMPORAL_TRANSITION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != TEMPORAL_TRANSITION_SCHEMA:
            raise CassiGroundedLanguageError("temporal transition schema mismatch")
        if self.action_id not in GROUND_ACTIONS:
            raise CassiGroundedLanguageError("temporal transition action is invalid")
        if not all(
            math.isfinite(value) and -1.0 <= value <= 1.0
            for value in (*self.before, *self.after)
        ):
            raise CassiGroundedLanguageError("temporal transition coordinate is invalid")

    @property
    def change_id(self) -> str:
        return change_from_coordinates(self.before, self.after)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiTemporalDecision:
    decision_kind: str
    answer_id: str
    answer_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    trajectory_work: tuple[tuple[str, float], ...]
    register_resonance: tuple[tuple[str, float], ...]
    selected_event_work: tuple[float, ...]
    state_sha256: str
    trained_memory_sha256: str
    schema: str = TEMPORAL_DECISION_SCHEMA

    def __post_init__(self) -> None:
        candidates = _TEMPORAL_CANDIDATES.get(self.decision_kind)
        if self.schema != TEMPORAL_DECISION_SCHEMA or candidates is None:
            raise CassiGroundedLanguageError("temporal decision schema or kind mismatch")
        if self.answer_id not in candidates:
            raise CassiGroundedLanguageError("temporal decision answer is invalid")
        for rows in (
            self.candidate_work,
            self.trajectory_work,
            self.register_resonance,
        ):
            if tuple(answer for answer, _ in rows) != candidates:
                raise CassiGroundedLanguageError("temporal candidate order is invalid")
        values = (
            self.answer_work,
            self.runner_up_work,
            self.margin,
            *(work for _, work in self.candidate_work),
            *(work for _, work in self.trajectory_work),
            *(work for _, work in self.register_resonance),
            *self.selected_event_work,
        )
        if not all(math.isfinite(value) for value in values):
            raise CassiGroundedLanguageError("temporal decision work is nonfinite")
        if self.answer_work <= 0.0 or self.margin <= 0.0:
            raise CassiGroundedLanguageError("temporal decision has no positive winner")

    @property
    def answer(self) -> str:
        return self.answer_id.split(".", 1)[1]

    def receipt_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "answer_id": self.answer_id,
            "answer_work": self.answer_work,
            "candidate_work": dict(self.candidate_work),
            "decision_kind": self.decision_kind,
            "margin": self.margin,
            "register_resonance": dict(self.register_resonance),
            "runner_up_work": self.runner_up_work,
            "schema": self.schema,
            "selected_event_work": list(self.selected_event_work),
            "state_sha256": self.state_sha256,
            "trained_memory_sha256": self.trained_memory_sha256,
            "trajectory_work": dict(self.trajectory_work),
        }


def decode_proprioception(observation: object) -> tuple[float, float]:
    if not isinstance(observation, (bytes, bytearray, memoryview)):
        raise CassiGroundedLanguageError("proprioceptive observation must be bytes")
    payload = bytes(observation)
    if len(payload) != 8:
        raise CassiGroundedLanguageError("proprioceptive observation must contain two f32 values")
    values = struct.unpack("<ff", payload)
    if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
        raise CassiGroundedLanguageError("proprioceptive observation is invalid")
    return values


def change_from_coordinates(
    before: tuple[float, float],
    after: tuple[float, float],
) -> str:
    delta_x = after[0] - before[0]
    delta_y = after[1] - before[1]
    tolerance = 1.0e-6
    if abs(delta_x) > tolerance and abs(delta_y) > tolerance:
        raise CassiGroundedLanguageError("temporal transition changed both axes")
    if delta_x < -tolerance:
        return "change.x-decrease"
    if delta_x > tolerance:
        return "change.x-increase"
    if delta_y > tolerance:
        return "change.y-increase"
    if delta_y < -tolerance:
        return "change.y-decrease"
    return "change.none"


def change_from_observations(
    before: bytes | bytearray | memoryview,
    after: bytes | bytearray | memoryview,
) -> str:
    return change_from_coordinates(
        decode_proprioception(before),
        decode_proprioception(after),
    )


def write_transition_register(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    *,
    before_observation: bytes,
    after_observation: bytes,
    action_id: str,
) -> QiFieldState:
    if action_id not in GROUND_ACTIONS:
        raise CassiGroundedLanguageError("temporal transition action is unknown")
    before = decode_proprioception(before_observation)
    after = decode_proprioception(after_observation)
    candidate = law.write_live_boundary_values(
        state,
        (*before, *after),
        offset=TEMPORAL_TRANSITION_OFFSET,
    )
    candidate = law.write_live_boundary_values(
        candidate,
        tuple(1.0 if action == action_id else 0.0 for action in GROUND_ACTIONS),
        offset=TEMPORAL_ACTION_OFFSET,
    )
    candidate = law.write_live_boundary_values(
        candidate,
        (0.0, 0.0, 0.0, 0.0),
        offset=TEMPORAL_ORDER_OFFSET,
    )
    return law.write_live_boundary_values(
        candidate,
        (1.0,),
        offset=TEMPORAL_VALID_OFFSET,
    )


def read_transition_register(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
) -> CassiTemporalTransition:
    valid = law.read_live_boundary_values(
        state,
        1,
        offset=TEMPORAL_VALID_OFFSET,
    )[0]
    if valid < 0.5:
        raise CassiGroundedLanguageError("no committed temporal transition is active")
    values = law.read_live_boundary_values(
        state,
        4,
        offset=TEMPORAL_TRANSITION_OFFSET,
    )
    action_values = law.read_live_boundary_values(
        state,
        len(GROUND_ACTIONS),
        offset=TEMPORAL_ACTION_OFFSET,
    )
    ranked = sorted(
        zip(GROUND_ACTIONS, action_values, strict=True),
        key=lambda item: (-item[1], item[0]),
    )
    if ranked[0][1] < 0.5 or ranked[0][1] - ranked[1][1] < 0.5:
        raise CassiGroundedLanguageError("temporal cause register is unresolved")
    return CassiTemporalTransition(
        before=(values[0], values[1]),
        after=(values[2], values[3]),
        action_id=ranked[0][0],
    )


def write_order_pair_register(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    first_state: tuple[float, float],
    second_state: tuple[float, float],
) -> QiFieldState:
    values = (*first_state, *second_state)
    if not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values):
        raise CassiGroundedLanguageError("temporal order state is invalid")
    return law.write_live_boundary_values(
        state,
        values,
        offset=TEMPORAL_ORDER_OFFSET,
    )


def read_order_pair_register(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
) -> tuple[tuple[float, float], tuple[float, float]]:
    values = law.read_live_boundary_values(
        state,
        4,
        offset=TEMPORAL_ORDER_OFFSET,
    )
    return (values[0], values[1]), (values[2], values[3])


def sense_temporal_prompt(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    prompt_kind: str,
    question: str,
) -> QiFieldState:
    return sense_grounded_symbols(
        law,
        state,
        codec.temporal_prompt_symbols(prompt_kind, question),
    )


def sense_prediction_prompt(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    question: str,
    action_id: str,
) -> QiFieldState:
    candidate = sense_temporal_prompt(
        law,
        state,
        codec,
        "prediction",
        question,
    )
    return sense_grounded_symbols(
        law,
        candidate,
        codec.action_symbols(action_id),
    )


def sense_order_question(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    first_state: tuple[float, float],
    second_state: tuple[float, float],
    question: str,
) -> QiFieldState:
    candidate = sense_grounded_symbols(
        law,
        state,
        codec.order_prompt_symbols(first_state, second_state, question),
    )
    return write_order_pair_register(
        law,
        candidate,
        first_state,
        second_state,
    )


def _select(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    *,
    decision_kind: str,
    symbol_fn: Callable[[str], tuple[int, ...]],
    register_scores: Mapping[str, float] | None = None,
    margin_floor: float = 0.5,
) -> CassiTemporalDecision:
    candidates = _TEMPORAL_CANDIDATES[decision_kind]
    trajectory_rows: list[tuple[str, float, tuple[float, ...]]] = []
    for answer_id in candidates:
        total, event_work = law.candidate_sequence_work(state, symbol_fn(answer_id))
        trajectory_rows.append((answer_id, total, event_work))
    resonance_rows = tuple(
        (answer_id, 0.0 if register_scores is None else float(register_scores[answer_id]))
        for answer_id in candidates
    )
    candidate_rows = [
        (
            answer_id,
            trajectory_work if register_scores is None else float(register_scores[answer_id]),
            event_work,
        )
        for answer_id, trajectory_work, event_work in trajectory_rows
    ]
    ranked = sorted(candidate_rows, key=lambda item: (-item[1], item[0]))
    winner, runner_up = ranked[:2]
    margin = winner[1] - runner_up[1]
    required = max(margin_floor, 1.0e-6 * abs(winner[1]))
    if winner[1] <= 0.0 or margin < required:
        raise CassiGroundedLanguageError(
            f"temporal {decision_kind} port did not resolve a winner"
        )
    return CassiTemporalDecision(
        decision_kind=decision_kind,
        answer_id=winner[0],
        answer_work=winner[1],
        runner_up_work=runner_up[1],
        margin=margin,
        candidate_work=tuple(
            (answer_id, work) for answer_id, work, _ in candidate_rows
        ),
        trajectory_work=tuple(
            (answer_id, work) for answer_id, work, _ in trajectory_rows
        ),
        register_resonance=resonance_rows,
        selected_event_work=winner[2],
        state_sha256=qi_state_sha256(controller, state),
        trained_memory_sha256=law.memory_sha256(state),
    )


def select_predicted_change(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
) -> CassiTemporalDecision:
    return _select(
        controller,
        law,
        state,
        decision_kind="prediction",
        symbol_fn=codec.change_symbols,
    )


def select_observed_change(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
) -> CassiTemporalDecision:
    transition = read_transition_register(law, state)
    scores = {change: 0.0 for change in GROUND_CHANGES}
    scores[transition.change_id] = 1.0
    return _select(
        controller,
        law,
        state,
        decision_kind="observed-change",
        symbol_fn=codec.change_symbols,
        register_scores=scores,
    )


def select_cause(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
) -> CassiTemporalDecision:
    transition = read_transition_register(law, state)
    cause_id = transition.action_id.replace("action.", "cause.")
    scores = {cause: 1.0 if cause == cause_id else 0.0 for cause in GROUND_CAUSES}
    return _select(
        controller,
        law,
        state,
        decision_kind="cause",
        symbol_fn=codec.cause_symbols,
        register_scores=scores,
    )


def select_time_target(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
) -> CassiTemporalDecision:
    return _select(
        controller,
        law,
        state,
        decision_kind="time-target",
        symbol_fn=codec.time_target_symbols,
    )


def select_order_position(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    target_id: str,
) -> CassiTemporalDecision:
    if target_id not in GROUND_TIME_TARGETS:
        raise CassiGroundedLanguageError("temporal order target is invalid")
    transition = read_transition_register(law, state)
    first, second = read_order_pair_register(law, state)
    target = transition.before if target_id == "time.before" else transition.after

    def score(candidate: tuple[float, float]) -> float:
        return max(0.0, 1.0 - max(abs(candidate[0] - target[0]), abs(candidate[1] - target[1])))

    scores = {
        "position.first": score(first),
        "position.second": score(second),
    }
    return _select(
        controller,
        law,
        state,
        decision_kind="order-position",
        symbol_fn=codec.order_position_symbols,
        register_scores=scores,
        margin_floor=0.01,
    )


def commit_temporal_decision(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    decision: CassiTemporalDecision,
) -> QiFieldState:
    symbol_fn: Mapping[str, Callable[[str], tuple[int, ...]]] = {
        "prediction": codec.change_symbols,
        "observed-change": codec.change_symbols,
        "cause": codec.cause_symbols,
        "time-target": codec.time_target_symbols,
        "order-position": codec.order_position_symbols,
    }
    symbols = symbol_fn[decision.decision_kind](decision.answer_id)
    if len(symbols) != len(decision.selected_event_work):
        raise CassiGroundedLanguageError("temporal decision work length mismatch")
    candidate = state
    for symbol, work in zip(symbols, decision.selected_event_work, strict=True):
        candidate, _ = law.react_event(candidate, symbol, work)
    return candidate


def render_causal_explanation(
    change_decision: CassiTemporalDecision,
    cause_decision: CassiTemporalDecision,
) -> str:
    if change_decision.decision_kind != "observed-change" or cause_decision.decision_kind != "cause":
        raise CassiGroundedLanguageError("causal explanation decisions are invalid")
    cause = cause_decision.answer_id.removeprefix("cause.")
    return f"{cause} caused {_CHANGE_TEXT[change_decision.answer_id]}"


__all__ = [
    "CassiTemporalDecision",
    "CassiTemporalTransition",
    "TEMPORAL_ACTION_OFFSET",
    "TEMPORAL_DECISION_SCHEMA",
    "TEMPORAL_ORDER_OFFSET",
    "TEMPORAL_TRANSITION_OFFSET",
    "TEMPORAL_TRANSITION_SCHEMA",
    "TEMPORAL_VALID_OFFSET",
    "change_from_coordinates",
    "change_from_observations",
    "commit_temporal_decision",
    "decode_proprioception",
    "read_order_pair_register",
    "read_transition_register",
    "render_causal_explanation",
    "select_cause",
    "select_observed_change",
    "select_order_position",
    "select_predicted_change",
    "select_time_target",
    "sense_order_question",
    "sense_prediction_prompt",
    "sense_temporal_prompt",
    "write_order_pair_register",
    "write_transition_register",
]
