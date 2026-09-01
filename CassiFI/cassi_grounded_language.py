"""Fixed grounded-language boundary and field-owned action port.

Text, world observations, actions, acknowledgments, and successor observations
share one ordered event stream. The helpers in this module contain no adaptive
state; every learned value remains in ``QiFieldState.field``.
"""
from __future__ import annotations

import dataclasses
import hashlib
import json
import math
import struct
from collections.abc import Mapping, Sequence

from cassi_field_language import (
    CassiFieldTextCodec,
    CassiQiTrajectoryLaw,
    qi_state_sha256,
)
from cassi_qi_field import QiFieldController, QiFieldState
from cassi_qi_world import (
    ZERO_SHA256,
    DeterministicQiWorld,
    QiActionCommand,
)

GROUND_BOUNDARY_SCHEMA = "cassi.qi-grounded-boundary.v4"
GROUND_ACTION_DECISION_SCHEMA = "cassi.qi-grounded-action-decision.v1"
GROUND_RELATION_DECISION_SCHEMA = "cassi.qi-grounded-relation-decision.v2"
GROUND_REFERENCE_DECISION_SCHEMA = "cassi.qi-grounded-reference-decision.v1"
GROUND_CONSOLIDATION_SCHEMA = "cassi.qi-grounded-consolidation.v1"
GROUND_CONSOLIDATION_STRENGTH_FLOOR = 0.8
GROUND_FRAME_PREFIX = b"QG1"
GROUND_ACTIONS = (
    "action.gaze-left",
    "action.gaze-right",
    "action.gaze-up",
    "action.gaze-down",
    "action.hold",
)
GROUND_ACTION_CODES = b"LRUDH"
GROUND_RELATIONS = (
    "relation.left",
    "relation.right",
    "relation.above",
    "relation.below",
    "relation.near",
    "relation.far",
)
GROUND_RELATION_CODES = b"LRABNF"
GROUND_OBJECT_COLORS = ("red", "blue", "green")
GROUND_OBJECT_COLOR_CODES = b"RBG"
GROUND_SPATIAL_GRID_SIZE = 5
GROUND_SPATIAL_RESONANCE_WEIGHT = 20.0
GROUND_RELATION_FAMILIES: Mapping[str, tuple[str, str]] = {
    "horizontal": ("relation.left", "relation.right"),
    "vertical": ("relation.above", "relation.below"),
    "distance": ("relation.near", "relation.far"),
}
GROUND_REFERENCES = tuple(
    f"reference.{color}" for color in GROUND_OBJECT_COLORS
)
GROUND_REFERENCE_CODES = GROUND_OBJECT_COLOR_CODES
GROUND_REFERENCE_ROLES = ("subject", "comparison")
GROUND_REFERENCE_ROLE_CODES = b"SC"
GROUND_ACTIVE_REFERENCE_OFFSET = 6
GROUND_REFERENCE_MARGIN_FLOOR = 0.5
GROUND_REFERENCE_TRAINING_STATEMENTS: Mapping[str, tuple[str, ...]] = {
    "reference.red": (
        "the name Alder refers to red",
        "use Birch for red",
    ),
    "reference.blue": (
        "the name Cedar refers to blue",
        "use Dahlia for blue",
    ),
    "reference.green": (
        "the name Elm refers to green",
        "use Fir for green",
    ),
}
GROUND_REFERENCE_HELDOUT_BINDINGS = (
    ("Mira", "let Mira refer to red", "reference.red"),
    ("Sable", "let Sable refer to blue", "reference.blue"),
    ("Orin", "let Orin refer to green", "reference.green"),
)
GROUND_REFERENCE_TRAINING_QUESTIONS: Mapping[str, tuple[str, ...]] = {
    "horizontal": (
        "resolve the horizontal relation",
        "which horizontal relation applies",
    ),
    "vertical": (
        "resolve the vertical relation",
        "which vertical relation applies",
    ),
    "distance": (
        "resolve the distance relation",
        "which distance relation applies",
    ),
}
GROUND_REFERENCE_HELDOUT_QUESTIONS: Mapping[str, str] = {
    "horizontal": "please decide the horizontal relation",
    "vertical": "please decide the vertical relation",
    "distance": "please decide the distance relation",
}
GROUND_CHANGES = (
    "change.x-decrease",
    "change.x-increase",
    "change.y-increase",
    "change.y-decrease",
    "change.none",
)
GROUND_CHANGE_CODES = b"LRUDH"
GROUND_CAUSES = tuple(action.replace("action.", "cause.") for action in GROUND_ACTIONS)
GROUND_CAUSE_CODES = GROUND_ACTION_CODES
GROUND_TIME_TARGETS = ("time.before", "time.after")
GROUND_TIME_TARGET_CODES = b"BA"
GROUND_ORDER_POSITIONS = ("position.first", "position.second")
GROUND_ORDER_POSITION_CODES = b"12"
GROUND_TEMPORAL_PROMPT_KINDS = (
    "prediction",
    "observed-change",
    "cause",
    "order",
)
GROUND_TEMPORAL_PROMPT_CODES = b"PCXO"
GROUND_PREDICTION_TRAINING_QUESTIONS = (
    "predict the resulting change",
    "what change follows this action",
)
GROUND_PREDICTION_HELDOUT_QUESTION = "what will change after this action"
GROUND_OBSERVED_CHANGE_QUESTION = "what changed after the last action"
GROUND_CAUSE_QUESTION = "what caused the last change"
GROUND_TIME_TRAINING_QUESTIONS: Mapping[str, tuple[str, ...]] = {
    "time.before": (
        "which presented state happened before",
        "select the earlier presented state",
    ),
    "time.after": (
        "which presented state happened after",
        "select the later presented state",
    ),
}
GROUND_TIME_HELDOUT_QUESTIONS: Mapping[str, str] = {
    "time.before": "which of these states came before",
    "time.after": "which of these states came after",
}
GROUND_SPATIAL_TRAINING_QUESTIONS: Mapping[str, tuple[str, ...]] = {
    "horizontal": (
        "is red left or right of blue",
        "which side is red from blue",
    ),
    "vertical": (
        "is red above or below blue",
        "where is red vertically from blue",
    ),
    "distance": (
        "are red and blue near or far",
        "how close is red to blue",
    ),
}
GROUND_SPATIAL_HELDOUT_QUESTIONS: Mapping[str, str] = {
    "horizontal": "please decide if red is left or right of blue",
    "vertical": "please decide if red is above or below blue",
    "distance": "please decide if red and blue are near or far",
}
GROUND_TRAINING_UTTERANCES: Mapping[str, tuple[str, ...]] = {
    "action.gaze-left": ("look left", "turn left"),
    "action.gaze-right": ("look right", "turn right"),
    "action.gaze-up": ("look up", "turn up"),
    "action.gaze-down": ("look down", "turn down"),
    "action.hold": ("hold still", "stay still"),
}
GROUND_HELDOUT_UTTERANCES: Mapping[str, str] = {
    "action.gaze-left": "turn your gaze left",
    "action.gaze-right": "turn your gaze right",
    "action.gaze-up": "raise your gaze up",
    "action.gaze-down": "lower your gaze down",
    "action.hold": "remain still",
}
_FRAME_KINDS = {
    "observation": 1,
    "action": 2,
    "acknowledgment": 3,
    "successor": 4,
    "objects": 5,
    "relation": 6,
    "binding": 7,
    "reference_cue": 8,
    "reference": 9,
    "temporal_prompt": 10,
    "change": 11,
    "cause": 12,
    "time_target": 13,
    "order_pair": 14,
    "order_position": 15,
}
_ACKNOWLEDGMENT_CODES: Mapping[str, bytes] = {
    "applied": b"A",
    "hold": b"H",
    "rejected": b"R",
    "expired": b"E",
}
_MAX_FRAME_BYTES = 65_535


class CassiGroundedLanguageError(RuntimeError):
    """Raised when grounded boundary or action selection is invalid."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class CassiGroundedActionDecision:
    action_id: str
    action_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    selected_event_work: tuple[float, ...]
    state_sha256: str
    trained_memory_sha256: str
    schema: str = GROUND_ACTION_DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != GROUND_ACTION_DECISION_SCHEMA:
            raise CassiGroundedLanguageError("grounded decision schema mismatch")
        if self.action_id not in GROUND_ACTIONS:
            raise CassiGroundedLanguageError("grounded decision action is unknown")
        if tuple(action for action, _ in self.candidate_work) != GROUND_ACTIONS:
            raise CassiGroundedLanguageError("grounded candidate order is invalid")
        values = (
            self.action_work,
            self.runner_up_work,
            self.margin,
            *(work for _, work in self.candidate_work),
            *self.selected_event_work,
        )
        if not all(math.isfinite(value) for value in values):
            raise CassiGroundedLanguageError("grounded decision work is nonfinite")
        if self.margin <= 0.0 or self.action_work <= 0.0:
            raise CassiGroundedLanguageError("grounded decision has no positive winner")

    def receipt_dict(self) -> dict[str, object]:
        return {
            "action_id": self.action_id,
            "action_work": self.action_work,
            "candidate_work": dict(self.candidate_work),
            "margin": self.margin,
            "runner_up_work": self.runner_up_work,
            "schema": self.schema,
            "selected_event_work": list(self.selected_event_work),
            "state_sha256": self.state_sha256,
            "trained_memory_sha256": self.trained_memory_sha256,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class CassiGroundedRelationDecision:
    relation_id: str
    relation_work: float
    runner_up_work: float
    margin: float
    family_id: str
    family_work: tuple[tuple[str, float], ...]
    candidate_work: tuple[tuple[str, float], ...]
    trajectory_work: tuple[tuple[str, float], ...]
    spatial_resonance: tuple[tuple[str, float], ...]
    subject_reference: str
    comparison_reference: str
    selected_event_work: tuple[float, ...]
    state_sha256: str
    trained_memory_sha256: str
    schema: str = GROUND_RELATION_DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != GROUND_RELATION_DECISION_SCHEMA:
            raise CassiGroundedLanguageError("grounded relation schema mismatch")
        if self.relation_id not in GROUND_RELATIONS:
            raise CassiGroundedLanguageError("grounded relation is unknown")
        if self.family_id not in GROUND_RELATION_FAMILIES:
            raise CassiGroundedLanguageError("grounded relation family is unknown")
        if self.relation_id not in GROUND_RELATION_FAMILIES[self.family_id]:
            raise CassiGroundedLanguageError("grounded relation is outside its family")
        if (
            self.subject_reference not in GROUND_REFERENCES
            or self.comparison_reference not in GROUND_REFERENCES
            or self.subject_reference == self.comparison_reference
        ):
            raise CassiGroundedLanguageError("grounded relation references are invalid")
        if tuple(family for family, _ in self.family_work) != tuple(
            GROUND_RELATION_FAMILIES
        ):
            raise CassiGroundedLanguageError("grounded relation family order is invalid")
        if tuple(relation for relation, _ in self.candidate_work) != GROUND_RELATIONS:
            raise CassiGroundedLanguageError("grounded relation order is invalid")
        if tuple(relation for relation, _ in self.trajectory_work) != GROUND_RELATIONS:
            raise CassiGroundedLanguageError("grounded trajectory work order is invalid")
        if tuple(relation for relation, _ in self.spatial_resonance) != GROUND_RELATIONS:
            raise CassiGroundedLanguageError("grounded spatial resonance order is invalid")
        values = (
            self.relation_work,
            self.runner_up_work,
            self.margin,
            *(work for _, work in self.family_work),
            *(work for _, work in self.candidate_work),
            *(work for _, work in self.trajectory_work),
            *(work for _, work in self.spatial_resonance),
            *self.selected_event_work,
        )
        if not all(math.isfinite(value) for value in values):
            raise CassiGroundedLanguageError("grounded relation work is nonfinite")
        if self.margin <= 0.0 or self.relation_work <= 0.0:
            raise CassiGroundedLanguageError("grounded relation has no positive winner")

    @property
    def answer(self) -> str:
        return self.relation_id.removeprefix("relation.")

    def receipt_dict(self) -> dict[str, object]:
        return {
            "answer": self.answer,
            "family_id": self.family_id,
            "family_work": dict(self.family_work),
            "candidate_work": dict(self.candidate_work),
            "spatial_resonance": dict(self.spatial_resonance),
            "trajectory_work": dict(self.trajectory_work),
            "subject_reference": self.subject_reference,
            "comparison_reference": self.comparison_reference,
            "margin": self.margin,
            "relation_id": self.relation_id,
            "relation_work": self.relation_work,
            "runner_up_work": self.runner_up_work,
            "schema": self.schema,
            "selected_event_work": list(self.selected_event_work),
            "state_sha256": self.state_sha256,
            "trained_memory_sha256": self.trained_memory_sha256,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class CassiGroundedReferenceDecision:
    reference_id: str
    reference_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]
    trajectory_work: tuple[tuple[str, float], ...]
    active_resonance: tuple[tuple[str, float], ...]
    selected_event_work: tuple[float, ...]
    used_active_register: bool
    state_sha256: str
    trained_memory_sha256: str
    schema: str = GROUND_REFERENCE_DECISION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != GROUND_REFERENCE_DECISION_SCHEMA:
            raise CassiGroundedLanguageError("grounded reference schema mismatch")
        if self.reference_id not in GROUND_REFERENCES:
            raise CassiGroundedLanguageError("grounded reference is unknown")
        if not isinstance(self.used_active_register, bool):
            raise CassiGroundedLanguageError("grounded reference register flag is invalid")
        for rows in (
            self.candidate_work,
            self.trajectory_work,
            self.active_resonance,
        ):
            if tuple(reference for reference, _ in rows) != GROUND_REFERENCES:
                raise CassiGroundedLanguageError("grounded reference order is invalid")
        values = (
            self.reference_work,
            self.runner_up_work,
            self.margin,
            *(work for _, work in self.candidate_work),
            *(work for _, work in self.trajectory_work),
            *(work for _, work in self.active_resonance),
            *self.selected_event_work,
        )
        if not all(math.isfinite(value) for value in values):
            raise CassiGroundedLanguageError("grounded reference work is nonfinite")
        if self.margin <= 0.0 or self.reference_work <= 0.0:
            raise CassiGroundedLanguageError("grounded reference has no positive winner")

    @property
    def color(self) -> str:
        return self.reference_id.removeprefix("reference.")

    def receipt_dict(self) -> dict[str, object]:
        return {
            "active_resonance": dict(self.active_resonance),
            "candidate_work": dict(self.candidate_work),
            "color": self.color,
            "margin": self.margin,
            "reference_id": self.reference_id,
            "reference_work": self.reference_work,
            "runner_up_work": self.runner_up_work,
            "schema": self.schema,
            "selected_event_work": list(self.selected_event_work),
            "state_sha256": self.state_sha256,
            "trained_memory_sha256": self.trained_memory_sha256,
            "trajectory_work": dict(self.trajectory_work),
            "used_active_register": self.used_active_register,
        }


@dataclasses.dataclass(frozen=True, slots=True)
class CassiGroundedConsolidation:
    desired_action_id: str
    residual: float
    trajectory_strength: float
    event_count: int
    memory_before_sha256: str
    memory_after_sha256: str
    outcome_observed: bool = True
    schema: str = GROUND_CONSOLIDATION_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != GROUND_CONSOLIDATION_SCHEMA:
            raise CassiGroundedLanguageError("grounded consolidation schema mismatch")
        if self.desired_action_id not in GROUND_ACTIONS:
            raise CassiGroundedLanguageError("grounded consolidation action is unknown")
        if (
            not math.isfinite(self.residual)
            or not 0.0 <= self.residual <= 1.0
            or not math.isfinite(self.trajectory_strength)
            or not 0.5 < self.trajectory_strength <= 1.0
            or self.event_count <= 0
            or not self.outcome_observed
        ):
            raise CassiGroundedLanguageError("grounded consolidation values are invalid")
        if self.memory_before_sha256 == self.memory_after_sha256:
            raise CassiGroundedLanguageError("grounded consolidation changed no memory")

    def receipt_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


class CassiGroundedEventCodec:
    """Non-adaptive typed framing over the canonical byte/control codec."""

    def __init__(self, text_codec: CassiFieldTextCodec | None = None) -> None:
        self.text = text_codec or CassiFieldTextCodec()
        self.fingerprint = _canonical_sha256(
            {
                "action_codes": {
                    action: GROUND_ACTION_CODES[index]
                    for index, action in enumerate(GROUND_ACTIONS)
                },
                "acknowledgment_codes": {
                    status: code[0]
                    for status, code in _ACKNOWLEDGMENT_CODES.items()
                },
                "object_color_codes": {
                    color: GROUND_OBJECT_COLOR_CODES[index]
                    for index, color in enumerate(GROUND_OBJECT_COLORS)
                },
                "reference_codes": {
                    reference: GROUND_REFERENCE_CODES[index]
                    for index, reference in enumerate(GROUND_REFERENCES)
                },
                "reference_roles": {
                    role: GROUND_REFERENCE_ROLE_CODES[index]
                    for index, role in enumerate(GROUND_REFERENCE_ROLES)
                },
                "relation_codes": {
                    relation: GROUND_RELATION_CODES[index]
                    for index, relation in enumerate(GROUND_RELATIONS)
                },
                "relation_families": {
                    family: list(relations)
                    for family, relations in GROUND_RELATION_FAMILIES.items()
                },
                "frame_kinds": _FRAME_KINDS,
                "frame_prefix_hex": GROUND_FRAME_PREFIX.hex(),
                "schema": GROUND_BOUNDARY_SCHEMA,
                "spatial_grid_size": GROUND_SPATIAL_GRID_SIZE,
                "spatial_resonance": {
                    "distance": "near=max(0,1-d);far=2d",
                    "direction": "positive-coordinate-difference",
                    "selection": "trajectory-family-then-resonance-only-answer",
                    "weight": GROUND_SPATIAL_RESONANCE_WEIGHT,
                },
                "active_reference_register": {
                    "offset": GROUND_ACTIVE_REFERENCE_OFFSET,
                    "width": len(GROUND_REFERENCES),
                },
                "reference_selection": {
                    "binding_memory": "statement-plus-subject-and-comparison-cues",
                    "explicit_margin_floor": GROUND_REFERENCE_MARGIN_FLOOR,
                    "pronoun": "active-register-only",
                },
                "temporal_outputs": {
                    "causes": {
                        cause: GROUND_CAUSE_CODES[index]
                        for index, cause in enumerate(GROUND_CAUSES)
                    },
                    "changes": {
                        change: GROUND_CHANGE_CODES[index]
                        for index, change in enumerate(GROUND_CHANGES)
                    },
                    "order_positions": {
                        position: GROUND_ORDER_POSITION_CODES[index]
                        for index, position in enumerate(GROUND_ORDER_POSITIONS)
                    },
                    "prompt_kinds": {
                        kind: GROUND_TEMPORAL_PROMPT_CODES[index]
                        for index, kind in enumerate(GROUND_TEMPORAL_PROMPT_KINDS)
                    },
                    "time_targets": {
                        target: GROUND_TIME_TARGET_CODES[index]
                        for index, target in enumerate(GROUND_TIME_TARGETS)
                    },
                },
                "text_codec_fingerprint": self.text.fingerprint,
            }
        )

    @staticmethod
    def _payload(value: bytes | bytearray | memoryview, name: str) -> bytes:
        if not isinstance(value, (bytes, bytearray, memoryview)):
            raise CassiGroundedLanguageError(f"{name} must be bytes")
        payload = bytes(value)
        if len(payload) > _MAX_FRAME_BYTES:
            raise CassiGroundedLanguageError(f"{name} exceeds the frame limit")

        return payload

    def frame_symbols(
        self,
        kind: str,
        payload: bytes | bytearray | memoryview,
    ) -> tuple[int, ...]:
        if kind not in _FRAME_KINDS or kind in {
            "action",
            "relation",
            "reference",
            "change",
            "cause",
            "time_target",
            "order_position",
        }:
            raise CassiGroundedLanguageError("inbound grounded frame kind is invalid")
        body = self._payload(payload, "grounded frame")
        raw = (
            GROUND_FRAME_PREFIX
            + bytes((_FRAME_KINDS[kind],))
            + len(body).to_bytes(2, "big")
            + body
        )
        return (self.text.system_symbol, *raw, self.text.end_turn_symbol)

    def _prompt_symbols(
        self,
        frame_kind: str,
        observation: bytes | bytearray | memoryview,
        utterance: str,
    ) -> tuple[int, ...]:
        if not isinstance(utterance, str) or not utterance:
            raise CassiGroundedLanguageError("grounded utterance must be nonempty text")
        encoded = utterance.encode("utf-8", errors="strict")
        if len(encoded) > 4096:
            raise CassiGroundedLanguageError("grounded utterance exceeds 4096 UTF-8 bytes")
        return (
            *self.frame_symbols(frame_kind, observation),
            self.text.user_symbol,
            *encoded,
            self.text.end_turn_symbol,
            self.text.assistant_symbol,
        )

    def instruction_symbols(
        self,
        predecessor_observation: bytes | bytearray | memoryview,
        utterance: str,
    ) -> tuple[int, ...]:
        return self._prompt_symbols("observation", predecessor_observation, utterance)

    def spatial_query_symbols(
        self,
        object_observation: bytes | bytearray | memoryview,
        question: str,
    ) -> tuple[int, ...]:
        return self._prompt_symbols("objects", object_observation, question)
    def binding_prompt_symbols(self, statement: str) -> tuple[int, ...]:
        return self._prompt_symbols("binding", b"", statement)

    def reference_cue_symbols(self, surface: str, role: str) -> tuple[int, ...]:
        if role not in GROUND_REFERENCE_ROLES:
            raise CassiGroundedLanguageError("grounded reference role is invalid")
        if not isinstance(surface, str) or not surface:
            raise CassiGroundedLanguageError("grounded reference surface is empty")
        encoded = surface.encode("utf-8", errors="strict")
        if len(encoded) > 512:
            raise CassiGroundedLanguageError("grounded reference surface is too long")
        payload = bytes(
            (GROUND_REFERENCE_ROLE_CODES[GROUND_REFERENCE_ROLES.index(role)],)
        ) + encoded
        return (*self.frame_symbols("reference_cue", payload), self.text.assistant_symbol)
    def temporal_prompt_symbols(
        self,
        prompt_kind: str,
        question: str,
    ) -> tuple[int, ...]:
        if prompt_kind not in GROUND_TEMPORAL_PROMPT_KINDS:
            raise CassiGroundedLanguageError("grounded temporal prompt kind is invalid")
        payload = bytes(
            (
                GROUND_TEMPORAL_PROMPT_CODES[
                    GROUND_TEMPORAL_PROMPT_KINDS.index(prompt_kind)
                ],
            )
        )
        return self._prompt_symbols("temporal_prompt", payload, question)

    def order_prompt_symbols(
        self,
        first_state: tuple[float, float],
        second_state: tuple[float, float],
        question: str,
    ) -> tuple[int, ...]:
        values = (*first_state, *second_state)
        if (
            len(first_state) != 2
            or len(second_state) != 2
            or not all(math.isfinite(value) and -1.0 <= value <= 1.0 for value in values)
        ):
            raise CassiGroundedLanguageError("grounded order state is invalid")
        return self._prompt_symbols(
            "order_pair",
            struct.pack("<ffff", *values),
            question,
        )



    def action_symbols(self, action_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_ACTIONS.index(action_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded action") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["action"],
            GROUND_ACTION_CODES[index],
            self.text.end_turn_symbol,
        )
    def relation_symbols(self, relation_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_RELATIONS.index(relation_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded relation") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["relation"],
            GROUND_RELATION_CODES[index],
            self.text.end_turn_symbol,
        )
    def reference_symbols(self, reference_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_REFERENCES.index(reference_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded reference") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["reference"],
            GROUND_REFERENCE_CODES[index],
            self.text.end_turn_symbol,
        )
    def change_symbols(self, change_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_CHANGES.index(change_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded change") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["change"],
            GROUND_CHANGE_CODES[index],
            self.text.end_turn_symbol,
        )

    def cause_symbols(self, cause_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_CAUSES.index(cause_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded cause") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["cause"],
            GROUND_CAUSE_CODES[index],
            self.text.end_turn_symbol,
        )

    def time_target_symbols(self, target_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_TIME_TARGETS.index(target_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded time target") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["time_target"],
            GROUND_TIME_TARGET_CODES[index],
            self.text.end_turn_symbol,
        )

    def order_position_symbols(self, position_id: str) -> tuple[int, ...]:
        try:
            index = GROUND_ORDER_POSITIONS.index(position_id)
        except ValueError as error:
            raise CassiGroundedLanguageError("unknown grounded order position") from error
        return (
            *GROUND_FRAME_PREFIX,
            _FRAME_KINDS["order_position"],
            GROUND_ORDER_POSITION_CODES[index],
            self.text.end_turn_symbol,
        )




    def outcome_symbols(
        self,
        acknowledgment_status: str,
        successor_observation: bytes | bytearray | memoryview,
    ) -> tuple[int, ...]:
        if acknowledgment_status not in _ACKNOWLEDGMENT_CODES:
            raise CassiGroundedLanguageError("unknown world acknowledgment status")
        return (
            *self.frame_symbols(
                "acknowledgment",
                _ACKNOWLEDGMENT_CODES[acknowledgment_status],
            ),
            *self.frame_symbols("successor", successor_observation),
        )

    def episode_symbols(
        self,
        predecessor_observation: bytes,
        utterance: str,
        action_id: str,
        acknowledgment_status: str,
        successor_observation: bytes,
    ) -> tuple[int, ...]:
        return (
            *self.instruction_symbols(predecessor_observation, utterance),
            *self.action_symbols(action_id),
            *self.outcome_symbols(acknowledgment_status, successor_observation),
        )
    def spatial_episode_symbols(
        self,
        object_observation: bytes,
        question: str,
        relation_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.spatial_query_symbols(object_observation, question),
            *self.relation_symbols(relation_id),
        )
    def binding_episode_symbols(
        self,
        statement: str,
        reference_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.binding_prompt_symbols(statement),
            *self.reference_symbols(reference_id),
        )

    def reference_episode_symbols(
        self,
        surface: str,
        role: str,
        reference_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.reference_cue_symbols(surface, role),
            *self.reference_symbols(reference_id),
        )
    def prediction_episode_symbols(
        self,
        predecessor_observation: bytes,
        instruction: str,
        action_id: str,
        question: str,
        change_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.instruction_symbols(predecessor_observation, instruction),
            *self.action_symbols(action_id),
            *self.temporal_prompt_symbols("prediction", question),
            *self.action_symbols(action_id),
            *self.change_symbols(change_id),
        )

    def time_target_episode_symbols(
        self,
        first_state: tuple[float, float],
        second_state: tuple[float, float],
        question: str,
        target_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.order_prompt_symbols(first_state, second_state, question),
            *self.time_target_symbols(target_id),
        )





def observe_proprioception(world: DeterministicQiWorld) -> bytes:
    observations = world.observe(
        world.logical_tick,
        {
            "frontier_sha256": ZERO_SHA256,
            "journal_head_sha256": ZERO_SHA256,
            "committed_cursor_sha256": ZERO_SHA256,
        },
        ("proprioceptive",),
    )
    if len(observations) != 1 or observations[0].modality != "proprioceptive":
        raise CassiGroundedLanguageError("world returned no proprioceptive observation")
    return observations[0].data
def _spatial_bin(value: float) -> int:
    if not math.isfinite(value) or not -1.0 <= value <= 1.0:
        raise CassiGroundedLanguageError("world object coordinate lies outside sensor bounds")
    return min(
        GROUND_SPATIAL_GRID_SIZE - 1,
        int((value + 1.0) * GROUND_SPATIAL_GRID_SIZE / 2.0),
    )


def observe_colored_objects(world: DeterministicQiWorld) -> bytes:
    objects = world.objects
    if len(objects) < len(GROUND_OBJECT_COLORS):
        raise CassiGroundedLanguageError("world exposes fewer than three objects")
    payload = bytearray((GROUND_SPATIAL_GRID_SIZE, len(GROUND_OBJECT_COLORS)))
    for code, (x, y, _, _, _) in zip(
        GROUND_OBJECT_COLOR_CODES,
        objects,
        strict=False,
    ):
        payload.extend((code, _spatial_bin(x), _spatial_bin(y)))
    return bytes(payload)


def decode_colored_objects(
    observation: bytes | bytearray | memoryview,
) -> tuple[tuple[str, int, int], ...]:
    payload = CassiGroundedEventCodec._payload(observation, "colored object observation")
    expected_count = len(GROUND_OBJECT_COLORS)
    if (
        len(payload) != 2 + 3 * expected_count
        or payload[0] != GROUND_SPATIAL_GRID_SIZE
        or payload[1] != expected_count
    ):
        raise CassiGroundedLanguageError("colored object observation shape is invalid")
    result: list[tuple[str, int, int]] = []
    for index, color in enumerate(GROUND_OBJECT_COLORS):
        offset = 2 + 3 * index
        if payload[offset] != GROUND_OBJECT_COLOR_CODES[index]:
            raise CassiGroundedLanguageError("colored object identity order is invalid")
        x_bin, y_bin = payload[offset + 1], payload[offset + 2]
        if x_bin >= GROUND_SPATIAL_GRID_SIZE or y_bin >= GROUND_SPATIAL_GRID_SIZE:
            raise CassiGroundedLanguageError("colored object coordinate is invalid")
        result.append((color, x_bin, y_bin))
    return tuple(result)


def spatial_relation_from_observation(
    observation: bytes | bytearray | memoryview,
    family: str,
    *,
    subject_reference: str = "reference.red",
    comparison_reference: str = "reference.blue",
) -> str:
    objects = {
        f"reference.{color}": (x_bin, y_bin)
        for color, x_bin, y_bin in decode_colored_objects(observation)
    }
    if (
        subject_reference not in objects
        or comparison_reference not in objects
        or subject_reference == comparison_reference
    ):
        raise CassiGroundedLanguageError("spatial relation references are invalid")
    subject_x, subject_y = objects[subject_reference]
    comparison_x, comparison_y = objects[comparison_reference]
    if family == "horizontal":
        if subject_x == comparison_x:
            raise CassiGroundedLanguageError("horizontal relation is unresolved on the sensor grid")
        return "relation.left" if subject_x < comparison_x else "relation.right"
    if family == "vertical":
        if subject_y == comparison_y:
            raise CassiGroundedLanguageError("vertical relation is unresolved on the sensor grid")
        return "relation.above" if subject_y > comparison_y else "relation.below"
    if family == "distance":
        return (
            "relation.near"
            if max(abs(subject_x - comparison_x), abs(subject_y - comparison_y)) <= 1
            else "relation.far"
        )
    raise CassiGroundedLanguageError("unknown spatial relation family")




def make_grounded_action_command(
    world: DeterministicQiWorld,
    action_id: str,
    *,
    field_state_sha256: str,
) -> QiActionCommand:
    if action_id not in GROUND_ACTIONS:
        raise CassiGroundedLanguageError("unknown grounded action")
    descriptor = next(
        (
            item
            for item in world.describe_actions(world.logical_tick)
            if item.action_id == action_id
        ),
        None,
    )
    if descriptor is None:
        raise CassiGroundedLanguageError("world omitted a grounded action descriptor")
    if action_id == "action.hold":
        requested_values: tuple[tuple[str, float], ...] = ()
    else:
        channel = (
            "gaze.yaw"
            if action_id.endswith(("left", "right"))
            else "gaze.pitch"
        )
        requested_values = ((channel, 1.0),)
    return QiActionCommand.make(
        world_id=world.world_id,
        episode_id=world.episode_id,
        action_id=action_id,
        logical_tick=world.logical_tick,
        requested_values=requested_values,
        profile_sha256=world.profile_sha256,
        descriptor_sha256=descriptor.descriptor_sha256,
        state_before_sha256=field_state_sha256,
        current_sha256=world.state_sha256,
        target_actuator=descriptor.target_actuator,
        body_frame_id=world.body_frame_id,
        session_id=world.session_id,
        cycle_number=world.logical_tick,
        committed_prior_head_sha256=ZERO_SHA256,
    )


def sense_grounded_symbols(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    symbols: Sequence[int],
) -> QiFieldState:
    candidate = state
    for symbol in symbols:
        candidate, _ = law.sense_event(candidate, int(symbol))
    return candidate


def select_grounded_action(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
) -> CassiGroundedActionDecision:
    candidate_rows: list[tuple[str, float, tuple[float, ...]]] = []
    for action_id in GROUND_ACTIONS:
        total, event_work = law.candidate_sequence_work(
            state,
            codec.action_symbols(action_id),
        )
        candidate_rows.append((action_id, total, event_work))
    ranked = sorted(candidate_rows, key=lambda item: (-item[1], item[0]))
    winner, runner_up = ranked[0], ranked[1]
    margin = winner[1] - runner_up[1]
    required = max(1.0e-6, 1.0e-6 * abs(winner[1]))
    if winner[1] <= 0.0 or margin <= required:
        raise CassiGroundedLanguageError("grounded action port did not resolve a winner")
    return CassiGroundedActionDecision(
        action_id=winner[0],
        action_work=winner[1],
        runner_up_work=runner_up[1],
        margin=margin,
        candidate_work=tuple((action, work) for action, work, _ in candidate_rows),
        selected_event_work=winner[2],
        state_sha256=qi_state_sha256(controller, state),
        trained_memory_sha256=law.memory_sha256(state),
    )


def commit_grounded_action(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    decision: CassiGroundedActionDecision,
) -> QiFieldState:
    symbols = codec.action_symbols(decision.action_id)
    if len(symbols) != len(decision.selected_event_work):
        raise CassiGroundedLanguageError("grounded action work length mismatch")
    candidate = state
    for symbol, work in zip(symbols, decision.selected_event_work, strict=True):
        candidate, _ = law.react_event(candidate, symbol, work)
    return candidate
def sense_binding_statement(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    statement: str,
) -> QiFieldState:
    return sense_grounded_symbols(law, state, codec.binding_prompt_symbols(statement))


def sense_reference_cue(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    surface: str,
    role: str,
) -> QiFieldState:
    return sense_grounded_symbols(
        law,
        state,
        codec.reference_cue_symbols(surface, role),
    )


def set_active_reference(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    reference_id: str,
) -> QiFieldState:
    if reference_id not in GROUND_REFERENCES:
        raise CassiGroundedLanguageError("active grounded reference is unknown")
    values = tuple(
        1.0 if candidate == reference_id else 0.0
        for candidate in GROUND_REFERENCES
    )
    return law.write_live_boundary_values(
        state,
        values,
        offset=GROUND_ACTIVE_REFERENCE_OFFSET,
    )


def read_active_reference(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
) -> str:
    values = law.read_live_boundary_values(
        state,
        len(GROUND_REFERENCES),
        offset=GROUND_ACTIVE_REFERENCE_OFFSET,
    )
    ranked = sorted(
        zip(GROUND_REFERENCES, values, strict=True),
        key=lambda item: (-item[1], item[0]),
    )
    if ranked[0][1] < 0.5 or ranked[0][1] - ranked[1][1] < 0.5:
        raise CassiGroundedLanguageError("active grounded reference is unresolved")
    return ranked[0][0]


def select_grounded_reference(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    *,
    use_active_register: bool = False,
) -> CassiGroundedReferenceDecision:
    trajectory_rows: list[tuple[str, float, tuple[float, ...]]] = []
    for reference_id in GROUND_REFERENCES:
        total, event_work = law.candidate_sequence_work(
            state,
            codec.reference_symbols(reference_id),
        )
        trajectory_rows.append((reference_id, total, event_work))
    active_values = law.read_live_boundary_values(
        state,
        len(GROUND_REFERENCES),
        offset=GROUND_ACTIVE_REFERENCE_OFFSET,
    )
    active_rows = tuple(zip(GROUND_REFERENCES, active_values, strict=True))
    candidate_rows = [
        (
            reference,
            active_values[index] if use_active_register else trajectory_work,
            event_work,
        )
        for index, (reference, trajectory_work, event_work) in enumerate(
            trajectory_rows
        )
    ]
    ranked = sorted(candidate_rows, key=lambda item: (-item[1], item[0]))
    winner, runner_up = ranked[:2]
    margin = winner[1] - runner_up[1]
    required = (
        0.5
        if use_active_register
        else max(
            GROUND_REFERENCE_MARGIN_FLOOR,
            1.0e-6 * abs(winner[1]),
        )
    )
    if winner[1] <= 0.0 or margin < required:
        raise CassiGroundedLanguageError("grounded reference port did not resolve a winner")
    return CassiGroundedReferenceDecision(
        reference_id=winner[0],
        reference_work=winner[1],
        runner_up_work=runner_up[1],
        margin=margin,
        candidate_work=tuple(
            (reference, work) for reference, work, _ in candidate_rows
        ),
        trajectory_work=tuple(
            (reference, work) for reference, work, _ in trajectory_rows
        ),
        active_resonance=active_rows,
        selected_event_work=winner[2],
        used_active_register=use_active_register,
        state_sha256=qi_state_sha256(controller, state),
        trained_memory_sha256=law.memory_sha256(state),
    )


def commit_grounded_reference(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    decision: CassiGroundedReferenceDecision,
) -> QiFieldState:
    symbols = codec.reference_symbols(decision.reference_id)
    if len(symbols) != len(decision.selected_event_work):
        raise CassiGroundedLanguageError("grounded reference work length mismatch")
    candidate = state
    for symbol, work in zip(symbols, decision.selected_event_work, strict=True):
        candidate, _ = law.react_event(candidate, symbol, work)
    return candidate


def consolidate_reference_binding(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    *,
    name: str,
    statement: str,
    reference_id: str,
) -> tuple[QiFieldState, int]:
    if not isinstance(name, str) or not name:
        raise CassiGroundedLanguageError("grounded binding name is empty")
    if name.casefold() not in statement.casefold():
        raise CassiGroundedLanguageError("grounded binding statement omits its name")
    sequences = (
        codec.binding_episode_symbols(statement, reference_id),
        codec.reference_episode_symbols(name, "subject", reference_id),
        codec.reference_episode_symbols(name, "comparison", reference_id),
    )
    candidate = state
    event_count = 0
    for sequence in sequences:
        candidate = law.learn_sequence(candidate, sequence, strength=1.0)
        event_count += len(sequence)
    return set_active_reference(law, candidate, reference_id), event_count


def sense_spatial_query(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    codec: CassiGroundedEventCodec,
    object_observation: bytes,
    question: str,
) -> QiFieldState:
    candidate = sense_grounded_symbols(
        law,
        state,
        codec.spatial_query_symbols(object_observation, question),
    )
    values = tuple(
        coordinate / (GROUND_SPATIAL_GRID_SIZE - 1)
        for _, x_bin, y_bin in decode_colored_objects(object_observation)
        for coordinate in (x_bin, y_bin)
    )
    return law.write_live_boundary_values(candidate, values)


def select_spatial_relation(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    *,
    subject_reference: str = "reference.red",
    comparison_reference: str = "reference.blue",
    family_id: str | None = None,
) -> CassiGroundedRelationDecision:
    if (
        subject_reference not in GROUND_REFERENCES
        or comparison_reference not in GROUND_REFERENCES
        or subject_reference == comparison_reference
    ):
        raise CassiGroundedLanguageError("spatial relation references are invalid")
    trajectory_rows: list[tuple[str, float, tuple[float, ...]]] = []
    for relation_id in GROUND_RELATIONS:
        total, event_work = law.candidate_sequence_work(
            state,
            codec.relation_symbols(relation_id),
        )
        trajectory_rows.append((relation_id, total, event_work))
    values = law.read_live_boundary_values(state, 2 * len(GROUND_REFERENCES))
    coordinates = {
        reference: values[2 * index : 2 * index + 2]
        for index, reference in enumerate(GROUND_REFERENCES)
    }
    subject_x, subject_y = coordinates[subject_reference]
    comparison_x, comparison_y = coordinates[comparison_reference]
    distance = max(
        abs(subject_x - comparison_x),
        abs(subject_y - comparison_y),
    )
    resonance_by_relation = {
        "relation.left": max(0.0, comparison_x - subject_x),
        "relation.right": max(0.0, subject_x - comparison_x),
        "relation.above": max(0.0, subject_y - comparison_y),
        "relation.below": max(0.0, comparison_y - subject_y),
        "relation.near": max(0.0, 1.0 - distance),
        "relation.far": 2.0 * distance,
    }
    trajectory_by_relation = {
        relation: work for relation, work, _ in trajectory_rows
    }
    family_rows = tuple(
        (
            family,
            max(trajectory_by_relation[relation] for relation in relations),
        )
        for family, relations in GROUND_RELATION_FAMILIES.items()
    )
    selected_family = family_id
    if selected_family is None:
        ranked_families = sorted(family_rows, key=lambda item: (-item[1], item[0]))
        family_winner, family_runner_up = ranked_families[:2]
        family_required = max(1.0e-6, 1.0e-6 * abs(family_winner[1]))
        if (
            family_winner[1] <= 0.0
            or family_winner[1] - family_runner_up[1] <= family_required
        ):
            raise CassiGroundedLanguageError("spatial question family did not resolve")
        selected_family = family_winner[0]
    elif selected_family not in GROUND_RELATION_FAMILIES:
        raise CassiGroundedLanguageError("unknown spatial relation family")
    selected_relations = GROUND_RELATION_FAMILIES[selected_family]
    candidate_rows = [
        (
            relation,
            GROUND_SPATIAL_RESONANCE_WEIGHT * resonance_by_relation[relation],
            event_work,
        )
        for relation, _, event_work in trajectory_rows
    ]
    ranked = sorted(
        (row for row in candidate_rows if row[0] in selected_relations),
        key=lambda item: (-item[1], item[0]),
    )
    winner, runner_up = ranked
    margin = winner[1] - runner_up[1]
    required = max(1.0e-6, 1.0e-6 * abs(winner[1]))
    if winner[1] <= 0.0 or margin <= required:
        raise CassiGroundedLanguageError("spatial relation port did not resolve a winner")
    return CassiGroundedRelationDecision(
        relation_id=winner[0],
        relation_work=winner[1],
        runner_up_work=runner_up[1],
        margin=margin,
        candidate_work=tuple(
            (relation, work) for relation, work, _ in candidate_rows
        ),
        family_id=selected_family,
        family_work=family_rows,
        selected_event_work=winner[2],
        spatial_resonance=tuple(
            (relation, resonance_by_relation[relation]) for relation in GROUND_RELATIONS
        ),
        subject_reference=subject_reference,
        comparison_reference=comparison_reference,
        state_sha256=qi_state_sha256(controller, state),
        trained_memory_sha256=law.memory_sha256(state),
        trajectory_work=tuple(
            (relation, work) for relation, work, _ in trajectory_rows
        ),
    )


def commit_spatial_relation(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    decision: CassiGroundedRelationDecision,
) -> QiFieldState:
    symbols = codec.relation_symbols(decision.relation_id)
    if len(symbols) != len(decision.selected_event_work):
        raise CassiGroundedLanguageError("spatial relation work length mismatch")
    candidate = state
    for symbol, work in zip(symbols, decision.selected_event_work, strict=True):
        candidate, _ = law.react_event(candidate, symbol, work)
    return candidate




def grounded_residual_and_strength(
    decision: CassiGroundedActionDecision,
    desired_action_id: str,
    *,
    required_margin: float = 0.25,
) -> tuple[float, float]:
    if desired_action_id not in GROUND_ACTIONS:
        raise CassiGroundedLanguageError("desired grounded action is unknown")
    if not math.isfinite(required_margin) or required_margin <= 0.0:
        raise CassiGroundedLanguageError("required grounded margin must be positive")
    work = dict(decision.candidate_work)
    desired = work[desired_action_id]
    best_competitor = max(
        value for action, value in decision.candidate_work if action != desired_action_id
    )
    scale = max(1.0, abs(desired), abs(best_competitor))
    residual = min(
        1.0,
        max(0.0, (best_competitor + required_margin - desired) / scale),
    )
    return residual, GROUND_CONSOLIDATION_STRENGTH_FLOOR + (
        1.0 - GROUND_CONSOLIDATION_STRENGTH_FLOOR
    ) * residual


def consolidate_grounded_episode(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    *,
    predecessor_observation: bytes,
    utterance: str,
    desired_action_id: str,
    acknowledgment_status: str,
    successor_observation: bytes,
    prediction: CassiGroundedActionDecision,
) -> tuple[QiFieldState, CassiGroundedConsolidation]:
    causal_prefix = (
        *codec.instruction_symbols(predecessor_observation, utterance),
        *codec.action_symbols(desired_action_id),
    )
    complete_episode = (
        *causal_prefix,
        *codec.outcome_symbols(
            acknowledgment_status,
            successor_observation,
        ),
    )
    residual, strength = grounded_residual_and_strength(
        prediction,
        desired_action_id,
    )
    memory_before = law.memory_sha256(state)
    successor = law.learn_sequence(state, causal_prefix, strength=1.0)
    successor = law.learn_sequence(
        successor,
        complete_episode,
        strength=strength,
    )
    receipt = CassiGroundedConsolidation(
        desired_action_id=desired_action_id,
        residual=residual,
        trajectory_strength=strength,
        event_count=len(causal_prefix) + len(complete_episode),
        memory_before_sha256=memory_before,
        memory_after_sha256=law.memory_sha256(successor),
    )
    return successor, receipt
def consolidate_spatial_episode(
    law: CassiQiTrajectoryLaw,
    codec: CassiGroundedEventCodec,
    state: QiFieldState,
    *,
    object_observation: bytes,
    question: str,
    relation_id: str,
) -> QiFieldState:
    return law.learn_sequence(
        state,
        codec.spatial_episode_symbols(object_observation, question, relation_id),
        strength=1.0,
    )




__all__ = [
    "CassiGroundedActionDecision",
    "CassiGroundedConsolidation",
    "CassiGroundedEventCodec",
    "CassiGroundedLanguageError",
    "CassiGroundedReferenceDecision",
    "CassiGroundedRelationDecision",
    "GROUND_ACTIONS",
    "GROUND_ACTION_CODES",
    "GROUND_BOUNDARY_SCHEMA",
    "GROUND_CAUSES",
    "GROUND_CAUSE_CODES",
    "GROUND_CAUSE_QUESTION",
    "GROUND_CHANGES",
    "GROUND_CHANGE_CODES",
    "GROUND_OBSERVED_CHANGE_QUESTION",
    "GROUND_ORDER_POSITIONS",
    "GROUND_ORDER_POSITION_CODES",
    "GROUND_PREDICTION_HELDOUT_QUESTION",
    "GROUND_PREDICTION_TRAINING_QUESTIONS",
    "GROUND_TEMPORAL_PROMPT_CODES",
    "GROUND_TEMPORAL_PROMPT_KINDS",
    "GROUND_TIME_HELDOUT_QUESTIONS",
    "GROUND_TIME_TARGETS",
    "GROUND_TIME_TRAINING_QUESTIONS",
    "GROUND_CONSOLIDATION_STRENGTH_FLOOR",
    "GROUND_ACTIVE_REFERENCE_OFFSET",
    "GROUND_HELDOUT_UTTERANCES",
    "GROUND_OBJECT_COLORS",
    "GROUND_REFERENCE_HELDOUT_BINDINGS",
    "GROUND_REFERENCE_HELDOUT_QUESTIONS",
    "GROUND_REFERENCE_MARGIN_FLOOR",
    "GROUND_REFERENCE_ROLES",
    "GROUND_REFERENCE_TRAINING_QUESTIONS",
    "GROUND_REFERENCE_TRAINING_STATEMENTS",
    "GROUND_REFERENCES",
    "GROUND_RELATION_FAMILIES",
    "GROUND_RELATIONS",
    "GROUND_RELATION_CODES",
    "GROUND_SPATIAL_GRID_SIZE",
    "GROUND_SPATIAL_HELDOUT_QUESTIONS",
    "GROUND_SPATIAL_TRAINING_QUESTIONS",
    "GROUND_TRAINING_UTTERANCES",
    "GROUND_SPATIAL_RESONANCE_WEIGHT",
    "commit_grounded_action",
    "commit_grounded_reference",
    "commit_spatial_relation",
    "consolidate_grounded_episode",
    "consolidate_reference_binding",
    "consolidate_spatial_episode",
    "decode_colored_objects",
    "grounded_residual_and_strength",
    "make_grounded_action_command",
    "observe_colored_objects",
    "observe_proprioception",
    "read_active_reference",
    "select_grounded_action",
    "select_grounded_reference",
    "select_spatial_relation",
    "sense_spatial_query",
    "sense_binding_statement",
    "sense_reference_cue",
    "sense_grounded_symbols",
    "set_active_reference",
    "spatial_relation_from_observation",
]
