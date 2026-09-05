"""Field-owned whole-utterance semantic trajectories for CassiFI."""
from __future__ import annotations

import dataclasses
import hashlib
import itertools
import json
import re
from typing import Final, Sequence

from cassi_field_language import (
    FIELD_LIVE_REGISTER_SIZE,
    CassiFieldTextCodec,
    CassiQiTrajectoryLaw,
    qi_state_sha256,
)
from cassi_grounded_language import (
    CassiGroundedEventCodec,
    GROUND_ACTIONS,
    sense_grounded_symbols,
)
from cassi_qi_field import QiFieldController, QiFieldState

DISCOURSE_GOAL_SCHEMA: Final[str] = "cassi.qi-discourse-goal.v1"
DISCOURSE_FRAME_SCHEMA: Final[str] = "cassi.qi-discourse-frame.v1"
DISCOURSE_ROUTES: Final[tuple[str, ...]] = (
    "route.action",
    "route.action-alias-binding",
    "route.prediction",
    "route.spatial",
    "route.reference",
    "route.binding",
    "route.explanation",
    "route.ordering",
    "route.neutral",
    "route.goal-declaration",
    "route.goal-trigger",
    "route.abstain",
)
_FRAME_VALUE_BASE: Final[int] = 241
_FRAME_NONE: Final[int] = 253
_FRAME_END: Final[int] = 254
_FRAME_BEGIN: Final[int] = 255
_FRAME_WORD_LIMIT: Final[int] = 5
DISCOURSE_FRAME_MINIMUM_HISTORY: Final[int] = 32
_FRAME_FAMILIES: Final[tuple[str, ...]] = ("horizontal", "vertical", "distance")
_FRAME_REFERENCES: Final[tuple[str, ...]] = (
    "reference.red",
    "reference.blue",
    "reference.green",
)
_FRAME_SURFACES: Final[tuple[str, ...]] = (
    "surface.active",
    "surface.alias-1",
    "surface.alias-2",
    "surface.red",
    "surface.blue",
    "surface.green",
    "surface.unnamed",
)
_FRAME_PRESENTATIONS: Final[tuple[str, ...]] = ("forward", "reverse")
_FRAME_CLARIFICATIONS: Final[tuple[str, ...]] = (
    "ambiguous_action",
    "ambiguous_relation_family",
    "temporal_states_indistinguishable",
    "missing_referent",
    "missing_active_referent",
    "unsupported",
)

# These development examples are disjoint from the Blind Labyrinth names and
# exact prompt bank. They deposit only route ownership, never exam answers.
DISCOURSE_ROUTE_TRAINING_PROMPTS: Final[dict[str, tuple[str, ...]]] = {
    "route.action": (
        "shift the eyes left",
        "direct the gaze right",
        "move the view up",
        "keep your gaze still now",
        "please gaze downward",
    ),
    "route.action-alias-binding": (
        "starboard means look right",
        "portside means look left",
        "treat zenith as look up",
        "treat portside as look left",
        "let nadir mean look down",
        "let anchor mean hold still",
    ),
    "route.prediction": (
        "without moving forecast a left view",
        "predict what happens after looking down",
        "before moving predict what looking right will change",
        "before moving predict what looking left will change",
        "what happens if you gaze up",
        "what transition is expected next Candidate action: look right",
        "identify next transition Candidate action: look up",
        "state the change that should follow the action Candidate action: keep your gaze exactly where it is.",
        "what transition is expected next Earlier action: direct your gaze right.",
        "identify the next transition Earlier action: move your looking direction up.",
    ),
    "route.spatial": (
        "determine the horizontal placement of green and red",
        "settle the horizontal relation for green and blue",
        "settle the distance relation for green and blue",
        "identify distance placement of red",
        "decide whether green is above or below red",
        "are red and green far or near",
    ),
    "route.reference": (
        "which horizontal relation involves Ada and blue",
        "which vertical relation involves Beryl and green",
        "resolve the above-below relation from Bruno to red",
        "settle the distance placement of Cora against green",
        "place Felix horizontally against blue",
        "how far is it from green",
        "settle distance placement of Ada against blue",
        "settle vertical placement of it against blue",
    ),
    "route.binding": (
        "use Ada to mean red",
        "use Bevan to mean blue",
        "use Cora to mean green",
        "record Daria as the name for red",
        "record Elara as the name for blue",
        "record Farah as the name for green",
        "make Gia refer to red",
        "make Hira refer to blue",
        "make Inez refer to green",
        "correct the reference: Jora means red",
        "correct the reference: Kira means blue",
        "correct the reference: Lira means green",
        "revise Mera so it denotes red",
        "revise Nira so it denotes blue",
        "revise Osha so it denotes green",
        "replace the old reference for Pera with red",
        "replace the old reference for Qira with blue",
        "replace the old reference for Risa with green",
        "revise the name binding so Sera denotes red",
        "revise the name binding so Tera denotes blue",
        "revise the name binding so Ula denotes green",
    ),
    "route.explanation": (
        "identify the committed transition",
        "state the cause of the latest change",
        "report the coordinate change from the latest committed movement",
        "what made the gaze position change",
        "what action caused the transition",
        "explain the previous movement",
    ),
    "route.ordering": (
        "which state came first or second",
        "which state came second or first in reverse",
    ),
    "route.neutral": (
        "inspect the field and leave the scene unchanged",
        "acknowledge the field while taking no action",
        "observe without committing anything",
    ),
    "route.goal-declaration": (
        "remember this three-step order: look up; look right; look down",
        "store this deferred mission: look left; look down; hold still",
        "defer these actions until after restart: look down; look left; hold still",
    ),
    "route.goal-trigger": ("begin the stored mission",),
    "route.abstain": (
        "clarify this conflict: turn right and left together",
        "clarify this relation: is above or far from",
        "clarify timing because states that cannot be distinguished",
        "clarify reference to unnamed thing far from red",
        "clarify active reference: is it above blue please",
        "how many shadows fit in zero",
    ),
}

DISCOURSE_ROUTE_VALIDATION_PROMPTS: Final[dict[str, tuple[str, ...]]] = {
    "route.action": ("please look down", "keep your gaze still"),
    "route.action-alias-binding": (
        "eastward means look right",
        "treat westward as look left",
    ),
    "route.prediction": (
        "before acting predict what looking left will change",
        "what happens if you look up",
    ),
    "route.spatial": (
        "decide whether red is above or below blue",
        "are blue and red far or near",
    ),
    "route.reference": (
        "place Della horizontally against green",
        "how far is it from blue",
    ),
    "route.binding": (
        "from now on use Della to mean blue",
        "record Evan as the name for green",
        "make Hira refer to red",
        "correct the reference: Iona means green",
        "revise Jessa so it denotes blue",
        "replace the old reference for Kora with red",
        "revise the name binding so Luma denotes red",
    ),
    "route.explanation": (
        "what made that position change",
        "explain the last movement",
    ),
    "route.ordering": (
        "which state came first or second.",
        "which state came second or first please",
    ),
    "route.neutral": (
        "inspect the field and leave it unchanged",
        "acknowledge the field without taking action",
    ),
    "route.goal-declaration": (
        "remember this three-step order: look left; look down; hold still",
    ),
    "route.goal-trigger": ("begin",),
    "route.abstain": (
        "turn right and left at the same time",
        "decide whether red is above or far from blue",
        "order two states that cannot be distinguished",
        "is an unnamed thing far from red",
        "is it above blue before any reference exists",
        "how many dreams fit in zero",
    ),
}

DISCOURSE_ABSTAIN_CLARIFICATIONS: Final[dict[str, str]] = {
    "clarify this conflict: turn right and left together": "ambiguous_action",
    "turn right and left at the same time": "ambiguous_action",
    "clarify this relation: is above or far from": "ambiguous_relation_family",
    "decide whether red is above or far from blue": "ambiguous_relation_family",
    "clarify timing because states that cannot be distinguished": (
        "temporal_states_indistinguishable"
    ),
    "order two states that cannot be distinguished": (
        "temporal_states_indistinguishable"
    ),
    "clarify reference to unnamed thing far from red": "missing_referent",
    "is an unnamed thing far from red": "missing_referent",
    "clarify active reference: is it above blue please": (
        "missing_active_referent"
    ),
    "is it above blue before any reference exists": "missing_active_referent",
    "how many shadows fit in zero": "unsupported",
    "how many dreams fit in zero": "unsupported",
}
_BINDING_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\b(?:let\s+)?(?P<name>(?!(?:to|it)\b)[A-Za-z][A-Za-z'-]{0,63})\s+"
        r"(?:refer(?:s)?\s+to|mean(?:s)?|stand(?:s)?\s+for|is\s+now)\s+"

        r"(?:the\s+)?(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brecord\s+(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+as\s+"
        r"(?:the\s+)?name\s+for\s+(?:the\s+)?(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bfrom\s+now\s+on\s+use\s+(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+"
        r"to\s+mean\s+(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\buse\s+(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+to\s+mean\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bassociate\s+(?:the\s+name\s+)?"
        r"(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+with\s+(?:the\s+)?"
        r"(?P<color>red|blue|green)(?:\s+object)?\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bmake\s+(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+refer\s+to\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bcorrect\s+the\s+reference:\s*"
        r"(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+means\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brevise\s+the\s+name\s+binding\s+so\s+"
        r"(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+denotes\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\brevise\s+(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+so\s+"
        r"it\s+denotes\s+(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\bupdate\s+the\s+association\s+and\s+use\s+"
        r"(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+for\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\breplace\s+the\s+old\s+reference\s+for\s+"
        r"(?P<name>[A-Za-z][A-Za-z'-]{0,63})\s+with\s+"
        r"(?P<color>red|blue|green)\b",
        re.IGNORECASE,
    ),
)
_REFERENCE_SLOT = r"(?:[A-Za-z][A-Za-z'-]{0,63}|unnamed\s+object|it)"
_REFERENCE_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        rf"\bplace\s+(?P<subject>{_REFERENCE_SLOT})\s+"
        rf"(?:horizontally|vertically)\s+against\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bresolve\b.*?\bfrom\s+(?P<subject>{_REFERENCE_SLOT})\s+to\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bwhich\s+side\s+is\s+(?P<subject>{_REFERENCE_SLOT})\b.*?"
        rf"\bcompared\s+with\s+(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bsettle\b.*?\binvolving\s+(?P<subject>{_REFERENCE_SLOT})\s+and\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bwhich\b.*?\brelation\s+involves\s+"
        rf"(?P<subject>{_REFERENCE_SLOT})\s+and\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bsettle\b.*?\bplacement\s+of\s+"
        rf"(?P<subject>{_REFERENCE_SLOT})\s+against\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\bmeasure\s+the\s+separation\s+of\s+"
        rf"(?P<subject>{_REFERENCE_SLOT})\s+from\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?P<subject>{_REFERENCE_SLOT})\s+(?:versus|vs\.?)\s+"
        rf"(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:is|where\s+is|how\s+far\s+is|how\s+distant\s+is)\s+"
        rf"(?P<subject>{_REFERENCE_SLOT})\b.*?\b"
        rf"(?:of|to|than|from|with)\s+(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
    re.compile(
        rf"\b(?:are|is|compare)\s+(?P<subject>{_REFERENCE_SLOT})\s+"
        rf"(?:and|with)\s+(?P<comparison>{_REFERENCE_SLOT})\b",
        re.IGNORECASE,
    ),
)


_RELATION_FAMILY_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    (
        "horizontal",
        re.compile(
            r"\b(?:left|right|horizontal|horizontally|side)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "vertical",
        re.compile(
            r"\b(?:above|below|vertical|vertically|height|top|bottom)\b",
            re.IGNORECASE,
        ),
    ),
    (
        "distance",
        re.compile(
            r"\b(?:near|far|distance|separation|close|distant)\b",
            re.IGNORECASE,
        ),
    ),
)

_ACTION_SLOT_PATTERNS: Final[tuple[tuple[str, re.Pattern[str]], ...]] = (
    ("action.gaze-left", re.compile(r"\b(?:left|leftward)\b", re.IGNORECASE)),
    ("action.gaze-right", re.compile(r"\b(?:right|rightward)\b", re.IGNORECASE)),
    ("action.gaze-up", re.compile(r"\b(?:up|upward)\b", re.IGNORECASE)),
    ("action.gaze-down", re.compile(r"\b(?:down|downward)\b", re.IGNORECASE)),
    (
        "action.hold",
        re.compile(
            r"\b(?:hold|holding|still|remain|wait)\b|"
            r"\bno(?:[-\s]+gaze)?[-\s]+movement\b|"
            r"\bgaze\s+exactly\s+where\s+it\s+is\b|"
            r"\bcurrent\s+gaze\s+position\b",
            re.IGNORECASE,
        ),
    ),
)
_ACTION_ALIAS_PATTERNS: Final[tuple[re.Pattern[str], ...]] = (
    re.compile(
        r"\bwhen\s+i\s+say\s+(?P<alias>[A-Za-z][A-Za-z'-]{0,63})\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?:treat|let)\s+(?P<alias>[A-Za-z][A-Za-z'-]{0,63})\s+"
        r"(?:as|mean)\b",
        re.IGNORECASE,
    ),
    re.compile(
        r"\b(?P<alias>[A-Za-z][A-Za-z'-]{0,63})\s+means?\s+"
        r"(?:look|gaze|hold|remain)\b",
        re.IGNORECASE,
    ),
)
_PREDICTION_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:predict|prediction|forecast|expected|outcome|follows?|happens?)\b|"
    r"\bwithout\s+(?:moving|acting)\b|"
    r"\b(?:candidate|earlier)\s+action\b",
    re.IGNORECASE,
)
_EXPLANATION_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:observed|committed|cause|caused|responsible|previous|latest|explain)\b|"
    r"\bwhat\s+made\b",
    re.IGNORECASE,
)
_ACTION_COMMAND_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:shift|direct|move|keep|make|remain|look|gaze|eyes?|view|hold|wait)\b",
    re.IGNORECASE,
)
_ORDERING_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\bstate\b.*\b(?:first|second)\b|\b(?:first|second)\b.*\bstate\b",
    re.IGNORECASE,
)
_NEUTRAL_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:acknowledge|inspect|observe)\b",
    re.IGNORECASE,
)
_GOAL_DECLARATION_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"\b(?:remember|store|defer)\b.*\b(?:mission|order|actions)\b",
    re.IGNORECASE,
)
_GOAL_TRIGGER_MARKER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"^\s*begin(?:\s+the\s+stored\s+mission)?\s*[.!]?\s*$",
    re.IGNORECASE,
)


class CassiDiscourseLanguageError(RuntimeError):
    """Raised when a raw discourse route or field goal is unresolved."""


def _canonical_sha256(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
            "utf-8"
        )
    ).hexdigest()


@dataclasses.dataclass(frozen=True, slots=True)
class CassiDiscourseFrameTarget:
    route_id: str
    commit: bool
    action_id: str | None = None
    family_id: str | None = None
    binding_reference: str | None = None
    subject_slot: str | None = None
    comparison_slot: str | None = None
    presentation: str | None = None
    clarification: str | None = None
    schema: str = DISCOURSE_FRAME_SCHEMA

    def __post_init__(self) -> None:
        if self.route_id not in DISCOURSE_ROUTES:
            raise CassiDiscourseLanguageError("semantic frame route is unknown")
        if not isinstance(self.commit, bool):
            raise CassiDiscourseLanguageError("semantic frame commit must be boolean")
        expected_commit = self.route_id in {
            "route.action",
            "route.action-alias-binding",
            "route.binding",
            "route.goal-declaration",
            "route.goal-trigger",
        }
        if self.commit != expected_commit:
            raise CassiDiscourseLanguageError("semantic frame commit value is inconsistent")
        checks = (
            (self.action_id, GROUND_ACTIONS, "action"),
            (self.family_id, _FRAME_FAMILIES, "family"),
            (self.binding_reference, _FRAME_REFERENCES, "binding reference"),
            (self.subject_slot, _FRAME_SURFACES, "subject"),
            (self.comparison_slot, _FRAME_SURFACES, "comparison"),
            (self.presentation, _FRAME_PRESENTATIONS, "presentation"),
            (self.clarification, _FRAME_CLARIFICATIONS, "clarification"),
        )
        for value, allowed, label in checks:
            if value is not None and value not in allowed:
                raise CassiDiscourseLanguageError(f"semantic frame {label} is unknown")
        if self.route_id in {
            "route.action",
            "route.action-alias-binding",
            "route.prediction",
        }:
            if self.action_id is None:
                raise CassiDiscourseLanguageError("semantic frame action is missing")
        elif self.action_id is not None:
            raise CassiDiscourseLanguageError("semantic frame action is misplaced")
        if self.route_id in {"route.spatial", "route.reference"}:
            if self.family_id is None:
                raise CassiDiscourseLanguageError("semantic frame family is missing")
        elif self.family_id is not None:
            raise CassiDiscourseLanguageError("semantic frame family is misplaced")
        if self.route_id == "route.binding":
            if self.binding_reference is None or self.subject_slot is None:
                raise CassiDiscourseLanguageError("semantic frame binding slots are missing")
            if not self.subject_slot.startswith("surface.alias-"):
                raise CassiDiscourseLanguageError("semantic frame binding subject is invalid")
            if self.comparison_slot is not None:
                raise CassiDiscourseLanguageError("semantic frame binding comparison is misplaced")
        elif self.binding_reference is not None:
            raise CassiDiscourseLanguageError("semantic frame binding is misplaced")
        if self.route_id == "route.reference":
            if self.subject_slot is None or self.comparison_slot is None:
                raise CassiDiscourseLanguageError("semantic frame reference slots are missing")
            if self.subject_slot == self.comparison_slot:
                raise CassiDiscourseLanguageError("semantic frame reference slots must differ")
        elif self.route_id != "route.binding" and (
            self.subject_slot is not None or self.comparison_slot is not None
        ):
            raise CassiDiscourseLanguageError("semantic frame reference slots are misplaced")
        if (self.route_id == "route.ordering") != (self.presentation is not None):
            raise CassiDiscourseLanguageError("semantic frame presentation is misplaced")
        if (self.route_id == "route.abstain") != (self.clarification is not None):
            raise CassiDiscourseLanguageError("semantic frame clarification is misplaced")

    def receipt_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)
@dataclasses.dataclass(frozen=True, slots=True)
class CassiDiscourseFrameSlotDecision:
    slot: str
    value: str | bool | None
    field_work: float
    runner_up_work: float
    margin: float
    candidate_work: tuple[tuple[str, float], ...]

    def receipt_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


@dataclasses.dataclass(frozen=True, slots=True)
class CassiDiscourseFrameDecision:
    target: CassiDiscourseFrameTarget
    slots: tuple[CassiDiscourseFrameSlotDecision, ...]
    cue_state_sha256: tuple[str, ...]
    selected_window_index: int
    trained_memory_sha256: str
    schema: str = DISCOURSE_FRAME_SCHEMA

    def receipt_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "target": self.target.receipt_dict(),
            "slots": tuple(slot.receipt_dict() for slot in self.slots),
            "cue_state_sha256": self.cue_state_sha256,
            "selected_window_index": self.selected_window_index,
            "trained_memory_sha256": self.trained_memory_sha256,
        }

@dataclasses.dataclass(frozen=True, slots=True)
class CassiActionAliasDecision:
    alias: str
    action_id: str
    cue_accuracy: float
    cue_correct: int
    cue_total: int
    field_work: float
    candidate_work: tuple[tuple[str, str, float], ...]

    def receipt_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)




def _frame_value_symbol(values: Sequence[object], value: object | None) -> int:
    if value is None:
        return _FRAME_NONE
    try:
        return _FRAME_VALUE_BASE + values.index(value)
    except ValueError as error:
        raise CassiDiscourseLanguageError("semantic frame value is unknown") from error




@dataclasses.dataclass(frozen=True, slots=True)
class CassiDeferredGoalDecision:
    actions: tuple[str, str, str]
    goal_work: float
    runner_up_work: float
    margin: float
    candidate_count: int
    state_sha256: str
    trained_memory_sha256: str
    schema: str = DISCOURSE_GOAL_SCHEMA

    def receipt_dict(self) -> dict[str, object]:
        return dataclasses.asdict(self)


_ROUTE_ALIAS_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<=\s)(?!(?:Candidate|Earlier|State|A|B)\b)[A-Z][A-Za-z'-]*\b"
)
_ROUTE_NUMBER_PATTERN: Final[re.Pattern[str]] = re.compile(
    r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?"
)
_ROUTE_WORD_PATTERN: Final[re.Pattern[str]] = re.compile(r"[a-z0-9]+")


def _normalize_frame_text(value: str) -> str:
    normalized = value
    for pattern in _ACTION_ALIAS_PATTERNS:
        match = pattern.search(normalized)
        if match is not None:
            start, end = match.span("alias")
            normalized = f"{normalized[:start]}alias{normalized[end:]}"
            break
    normalized = _ROUTE_ALIAS_PATTERN.sub("alias", normalized)
    return _ROUTE_NUMBER_PATTERN.sub("number", normalized)


class CassiDiscourseEventCodec:
    """Whole-utterance field frames and persistent trajectory bindings."""

    def __init__(
        self,
        text_codec: CassiFieldTextCodec | None = None,
        grounded_codec: CassiGroundedEventCodec | None = None,
    ) -> None:
        self.text = text_codec or CassiFieldTextCodec()
        self.grounded = grounded_codec or CassiGroundedEventCodec(self.text)
        self.fingerprint = _canonical_sha256(
            {
                "goal_cue": "canonical-post-route-trigger",
                "goal_length": 3,
                "semantic_frame": "sliding-route-specific-atomic-frame-v3",
                "action_alias": "exact-field-trajectory-hash16-v1",
                "text_codec_fingerprint": self.text.fingerprint,
            }
        )

    @staticmethod
    def _text(value: str) -> bytes:
        if not isinstance(value, str) or not value.strip():
            raise CassiDiscourseLanguageError("discourse text must be nonempty")
        encoded = value.strip().encode("utf-8", errors="strict")
        if len(encoded) > 4096:
            raise CassiDiscourseLanguageError("discourse text exceeds 4096 UTF-8 bytes")
        return encoded

    @staticmethod
    def _frame_rows(
        target: CassiDiscourseFrameTarget,
    ) -> tuple[tuple[str, Sequence[object], object | None], ...]:
        rows: list[tuple[str, Sequence[object], object | None]] = [
            ("route", DISCOURSE_ROUTES, target.route_id),
            ("commit", (False, True), target.commit),
        ]
        if target.route_id in {
            "route.action",
            "route.action-alias-binding",
            "route.prediction",
        }:
            rows.append(("action", GROUND_ACTIONS, target.action_id))
        elif target.route_id in {"route.spatial", "route.reference"}:
            rows.append(("family", _FRAME_FAMILIES, target.family_id))
            if target.route_id == "route.reference":
                rows.extend(
                    (
                        ("subject", _FRAME_SURFACES, target.subject_slot),
                        ("comparison", _FRAME_SURFACES, target.comparison_slot),
                    )
                )
        elif target.route_id == "route.binding":
            rows.extend(
                (
                    (
                        "binding_reference",
                        _FRAME_REFERENCES,
                        target.binding_reference,
                    ),
                    ("subject", _FRAME_SURFACES, target.subject_slot),
                )
            )
        elif target.route_id == "route.ordering":
            rows.append(("presentation", _FRAME_PRESENTATIONS, target.presentation))
        elif target.route_id == "route.abstain":
            rows.append(
                ("clarification", _FRAME_CLARIFICATIONS, target.clarification)
            )
        return tuple(rows)

    def frame_symbols(self, target: CassiDiscourseFrameTarget) -> tuple[int, ...]:
        return (
            _FRAME_BEGIN,
            *(
                _frame_value_symbol(values, value)
                for _, values, value in self._frame_rows(target)
            ),
            _FRAME_END,
        )

    def _frame_prompt_windows(
        self,
        text: str,
        *,
        sliding: bool,
    ) -> tuple[tuple[int, ...], ...]:
        normalized = self._text(_normalize_frame_text(text)).decode("utf-8").casefold()
        words = _ROUTE_WORD_PATTERN.findall(normalized)
        if not words:
            raise CassiDiscourseLanguageError("discourse text contains no frame words")
        if sliding:
            starts = range(max(1, len(words) - _FRAME_WORD_LIMIT + 1))
        else:
            coarse = list(
                range(
                    0,
                    max(1, len(words) - _FRAME_WORD_LIMIT + 1),
                    _FRAME_WORD_LIMIT,
                )
            )
            last_start = max(0, len(words) - _FRAME_WORD_LIMIT)
            if coarse[-1] != last_start:
                coarse.append(last_start)
            starts = coarse
        windows: list[tuple[int, ...]] = []
        for start in starts:
            encoded = tuple(
                symbol
                for word in words[start : start + _FRAME_WORD_LIMIT]
                for symbol in hashlib.blake2s(
                    word.encode("utf-8"), digest_size=2
                ).digest()
            )
            cue = (
                self.text.user_symbol,
                *reversed(encoded),
                self.text.end_turn_symbol,
                self.text.assistant_symbol,
            )
            if cue not in windows:
                windows.append(cue)
        return tuple(windows)

    def frame_prompt_windows(self, text: str) -> tuple[tuple[int, ...], ...]:
        return self._frame_prompt_windows(text, sliding=True)

    def frame_training_windows(self, text: str) -> tuple[tuple[int, ...], ...]:
        return self._frame_prompt_windows(text, sliding=False)

    def frame_episode_sequences(
        self,
        text: str,
        target: CassiDiscourseFrameTarget,
    ) -> tuple[tuple[int, ...], ...]:
        frame = self.frame_symbols(target)
        return tuple(
            (*prompt, *frame)
            for prompt in self.frame_training_windows(text)
        )

    def action_alias_prompt_symbols(self, alias: str) -> tuple[int, ...]:
        normalized = alias.strip().casefold()
        if re.fullmatch(r"[a-z][a-z'-]{0,63}", normalized) is None:
            raise CassiDiscourseLanguageError("action alias is invalid")
        digest = hashlib.blake2s(normalized.encode("utf-8"), digest_size=2).digest()
        return (
            self.text.system_symbol,
            *b"CASSI_ACTION_ALIAS",
            *digest,
            self.text.end_turn_symbol,
            self.text.assistant_symbol,
        )

    def action_alias_episode_symbols(
        self,
        alias: str,
        action_id: str,
    ) -> tuple[int, ...]:
        return (
            *self.action_alias_prompt_symbols(alias),
            *self.grounded.action_symbols(action_id),
        )


    def goal_prompt_symbols(self) -> tuple[int, ...]:
        return (
            self.text.system_symbol,
            *b"CASSI_GOAL_BEGIN",
            self.text.end_turn_symbol,
            self.text.assistant_symbol,
        )

    def goal_plan_symbols(self, actions: Sequence[str]) -> tuple[int, ...]:
        if len(actions) != 3 or any(action not in GROUND_ACTIONS for action in actions):
            raise CassiDiscourseLanguageError("deferred goal must contain three actions")
        return tuple(
            symbol
            for action in actions
            for symbol in self.grounded.action_symbols(action)
        )

    def goal_episode_symbols(self, actions: Sequence[str]) -> tuple[int, ...]:
        return (*self.goal_prompt_symbols(), *self.goal_plan_symbols(actions))



def parse_binding(text: str) -> tuple[str, str]:
    for pattern in _BINDING_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group("name"), f"reference.{match.group('color').casefold()}"
    raise CassiDiscourseLanguageError("binding slots are unresolved")


def parse_reference_query(text: str) -> tuple[str, str]:
    for pattern in _REFERENCE_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group("subject"), match.group("comparison")
    raise CassiDiscourseLanguageError("reference-query slots are unresolved")


def _frame_label(value: object | None) -> str:
    if value is None:
        return "none"
    if isinstance(value, bool):
        return "true" if value else "false"
    return str(value)


def _frame_symbol_work(
    law: CassiQiTrajectoryLaw,
    states: Sequence[QiFieldState],
    symbol: int,
) -> tuple[float, tuple[float, ...]]:
    works = tuple(
        law.candidate_sequence_work(candidate, (symbol,))[1][0]
        for candidate in states
    )
    return sum(works) / len(works), works


def _advance_frame_symbol(
    law: CassiQiTrajectoryLaw,
    states: Sequence[QiFieldState],
    symbol: int,
    works: Sequence[float],
) -> tuple[QiFieldState, ...]:
    return tuple(
        law.react_event(candidate, symbol, work)[0]
        for candidate, work in zip(states, works, strict=True)
    )


def _advance_frame_boundary(
    law: CassiQiTrajectoryLaw,
    states: Sequence[QiFieldState],
    symbol: int,
) -> tuple[QiFieldState, ...]:
    field_work, works = _frame_symbol_work(law, states, symbol)
    if field_work <= 0.0:
        raise CassiDiscourseLanguageError("semantic frame boundary did not resolve")
    return _advance_frame_symbol(law, states, symbol, works)


def _select_frame_slot(
    law: CassiQiTrajectoryLaw,
    states: Sequence[QiFieldState],
    slot: str,
    values: Sequence[str | bool],
    candidates: Sequence[str | bool | None],
) -> tuple[
    str | bool | None,
    tuple[QiFieldState, ...],
    CassiDiscourseFrameSlotDecision,
]:
    if not candidates:
        raise CassiDiscourseLanguageError(f"semantic frame {slot} has no legal values")
    rows = tuple(
        (
            value,
            _frame_value_symbol(values, value),
            *_frame_symbol_work(
                law,
                states,
                _frame_value_symbol(values, value),
            ),
        )
        for value in candidates
    )
    ranked = sorted(rows, key=lambda item: (-item[2], _frame_label(item[0])))
    winner = ranked[0]
    runner_up_work = ranked[1][2] if len(ranked) > 1 else 0.0
    margin = winner[2] - runner_up_work
    required = max(1.0e-6, 1.0e-6 * abs(winner[2]))
    if winner[2] <= 0.0 or (len(ranked) > 1 and margin <= required):
        raise CassiDiscourseLanguageError(f"semantic frame {slot} did not resolve")
    return (
        winner[0],
        _advance_frame_symbol(
            law,
            states,
            winner[1],
            winner[3],
        ),
        CassiDiscourseFrameSlotDecision(
            slot=slot,
            value=winner[0],
            field_work=winner[2],
            runner_up_work=runner_up_work,
            margin=margin,
            candidate_work=tuple(
                (_frame_label(value), field_work)
                for value, _, field_work, _ in rows
            ),
        ),
    )


def _surface_frame_candidates(
    text: str,
) -> tuple[tuple[str, ...], tuple[str, ...], str | None, str | None]:
    actions = parse_action_candidates(text)
    families = tuple(
        family
        for family, pattern in _RELATION_FAMILY_PATTERNS
        if pattern.search(text)
    )
    family = families[0] if len(families) == 1 else None
    relation_ambiguous = len(families) > 1 or (
        not families and re.search(r"\brelation\b", text, re.IGNORECASE)
    )
    temporal_ambiguous = bool(
        re.search(
            r"\b(?:cannot be distinguished|indistinguishable)\b|"
            r"\bwhich\s+state\s+came\s+first\s+after\b",
            text,
            re.IGNORECASE,
        )
    )
    if len(actions) > 1:
        surface_clarification = "ambiguous_action"
    elif temporal_ambiguous:
        surface_clarification = "temporal_states_indistinguishable"
    elif re.search(r"\bunnamed\b", text, re.IGNORECASE):
        surface_clarification = "missing_referent"
    elif re.search(
        r"\b(?:before any reference exists|clarify active reference)\b",
        text,
        re.IGNORECASE,
    ):
        surface_clarification = "missing_active_referent"
    elif relation_ambiguous:
        surface_clarification = "ambiguous_relation_family"
    elif re.search(r"\bhow many\b.*\bzero\b", text, re.IGNORECASE):
        surface_clarification = "unsupported"
    else:
        surface_clarification = None
    try:
        reference_surfaces = parse_reference_query(text)
    except CassiDiscourseLanguageError:
        reference_marked = False
    else:
        reference_marked = any(
            surface.casefold() not in {"red", "blue", "green"}
            for surface in reference_surfaces
        )

    allowed: set[str] | None = None
    if any(pattern.search(text) for pattern in _ACTION_ALIAS_PATTERNS):
        allowed = {"route.action-alias-binding", "route.abstain"}
    else:
        try:
            parse_binding(text)
        except CassiDiscourseLanguageError:
            pass
        else:
            allowed = {"route.binding", "route.abstain"}

    prediction_marked = bool(_PREDICTION_MARKER_PATTERN.search(text))
    explanation_marked = bool(_EXPLANATION_MARKER_PATTERN.search(text))
    if allowed is None and _GOAL_DECLARATION_MARKER_PATTERN.search(text):
        allowed = {"route.goal-declaration", "route.abstain"}
    elif allowed is None and _GOAL_TRIGGER_MARKER_PATTERN.search(text):
        allowed = {"route.goal-trigger", "route.abstain"}
    elif allowed is None and surface_clarification is not None:
        allowed = {"route.abstain"}
    elif allowed is None and _ORDERING_MARKER_PATTERN.search(text):
        allowed = {"route.ordering", "route.abstain"}
    elif allowed is None and prediction_marked != explanation_marked:
        allowed = {
            "route.prediction" if prediction_marked else "route.explanation",
            "route.abstain",
        }
    elif (
        allowed is None
        and len(actions) == 1
        and _ACTION_COMMAND_MARKER_PATTERN.search(text)
    ):
        allowed = {"route.action", "route.abstain"}
    elif allowed is None and family is not None and reference_marked:
        allowed = {"route.reference", "route.abstain"}
    elif allowed is None and family is not None:
        allowed = {"route.spatial", "route.abstain"}
    elif allowed is None and _NEUTRAL_MARKER_PATTERN.search(text):
        allowed = {"route.neutral", "route.abstain"}

    routes = (
        DISCOURSE_ROUTES
        if allowed is None
        else tuple(route for route in DISCOURSE_ROUTES if route in allowed)
    )
    return routes, actions, family, surface_clarification


def _decode_discourse_frame_state(
    law: CassiQiTrajectoryLaw,
    state: QiFieldState,
    text: str,
) -> tuple[
    CassiDiscourseFrameTarget,
    tuple[CassiDiscourseFrameSlotDecision, ...],
    float,
]:
    working = _advance_frame_boundary(law, (state,), _FRAME_BEGIN)
    slot_decisions: list[CassiDiscourseFrameSlotDecision] = []

    def select(
        slot: str,
        values: Sequence[str | bool],
        candidates: Sequence[str | bool | None],
    ) -> str | bool | None:
        nonlocal working
        value, working, decision = _select_frame_slot(
            law,
            working,
            slot,
            values,
            candidates,
        )
        slot_decisions.append(decision)
        return value

    (
        route_candidates,
        surface_actions,
        surface_family,
        surface_clarification,
    ) = _surface_frame_candidates(text)
    route = select("route", DISCOURSE_ROUTES, route_candidates)
    if not isinstance(route, str):
        raise CassiDiscourseLanguageError("semantic frame route is invalid")
    route_id = route
    commit_value = select("commit", (False, True), (False, True))
    if not isinstance(commit_value, bool):
        raise CassiDiscourseLanguageError("semantic frame commit is invalid")

    action_value = None
    family_value = None
    binding_value = None
    subject_value = None
    comparison_value = None
    presentation_value = None
    clarification_value = None
    if route_id in {
        "route.action",
        "route.action-alias-binding",
        "route.prediction",
    }:
        action_value = select(
            "action",
            GROUND_ACTIONS,
            surface_actions if len(surface_actions) == 1 else GROUND_ACTIONS,
        )
    elif route_id in {"route.spatial", "route.reference"}:
        surface_families = (
            (surface_family,) if surface_family is not None else _FRAME_FAMILIES
        )
        family_value = select("family", _FRAME_FAMILIES, surface_families)
        if route_id == "route.reference":
            surfaces = tuple(frame_surface_candidates(text))
            if len(surfaces) < 2:
                raise CassiDiscourseLanguageError(
                    "semantic frame reference surfaces are missing"
                )
            subject_value = select("subject", _FRAME_SURFACES, surfaces)
            comparison_value = select(
                "comparison",
                _FRAME_SURFACES,
                tuple(surface for surface in surfaces if surface != subject_value),
            )
    elif route_id == "route.binding":
        binding_value = select(
            "binding_reference",
            _FRAME_REFERENCES,
            _FRAME_REFERENCES,
        )
        binding_surfaces = tuple(
            surface
            for surface in frame_surface_candidates(text)
            if surface.startswith("surface.alias-")
        )
        if not binding_surfaces:
            raise CassiDiscourseLanguageError(
                "semantic frame binding surface is missing"
            )
        subject_value = select("subject", _FRAME_SURFACES, binding_surfaces)
    elif route_id == "route.ordering":
        presentation_value = select(
            "presentation",
            _FRAME_PRESENTATIONS,
            _FRAME_PRESENTATIONS,
        )
    elif route_id == "route.abstain":
        clarification_candidates = (
            (surface_clarification,)
            if surface_clarification is not None
            else _FRAME_CLARIFICATIONS
        )
        clarification_value = select(
            "clarification",
            _FRAME_CLARIFICATIONS,
            clarification_candidates,
        )
    _advance_frame_boundary(law, working, _FRAME_END)

    target = CassiDiscourseFrameTarget(
        route_id=route_id,
        commit=commit_value,
        action_id=action_value if isinstance(action_value, str) else None,
        family_id=family_value if isinstance(family_value, str) else None,
        binding_reference=binding_value if isinstance(binding_value, str) else None,
        subject_slot=subject_value if isinstance(subject_value, str) else None,
        comparison_slot=(
            comparison_value if isinstance(comparison_value, str) else None
        ),
        presentation=(
            presentation_value if isinstance(presentation_value, str) else None
        ),
        clarification=(
            clarification_value if isinstance(clarification_value, str) else None
        ),
    )
    slots = tuple(slot_decisions)
    return target, slots, min(slot.margin for slot in slots)


def select_discourse_frame(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiDiscourseEventCodec,
    state: QiFieldState,
    text: str,
) -> CassiDiscourseFrameDecision:
    cue_states = tuple(
        sense_grounded_symbols(law, law.reset_context(state), symbols)
        for symbols in codec.frame_prompt_windows(text)
    )
    cue_state_sha256 = tuple(
        qi_state_sha256(controller, candidate) for candidate in cue_states
    )
    decoded: list[
        tuple[
            float,
            int,
            CassiDiscourseFrameTarget,
            tuple[CassiDiscourseFrameSlotDecision, ...],
        ]
    ] = []
    failures: list[CassiDiscourseLanguageError] = []
    for index, candidate in enumerate(cue_states):
        try:
            target, slots, score = _decode_discourse_frame_state(
                law,
                candidate,
                text,
            )
        except CassiDiscourseLanguageError as error:
            failures.append(error)
            continue
        decoded.append((score, index, target, slots))
    if not decoded:
        raise CassiDiscourseLanguageError(
            "semantic frame did not resolve from any utterance window"
        ) from (failures[0] if failures else None)
    _, selected_index, target, slots = min(
        decoded,
        key=lambda row: (-row[0], row[1]),
    )
    return CassiDiscourseFrameDecision(
        target=target,
        slots=slots,
        cue_state_sha256=cue_state_sha256,
        selected_window_index=selected_index,
        trained_memory_sha256=law.memory_sha256(state),
    )




def select_action_alias(
    law: CassiQiTrajectoryLaw,
    codec: CassiDiscourseEventCodec,
    state: QiFieldState,
    text: str,
) -> CassiActionAliasDecision | None:
    words = tuple(
        dict.fromkeys(re.findall(r"\b[a-z][a-z'-]{0,63}\b", text.casefold()))
    )
    resolved: list[
        tuple[
            str,
            str,
            float,
            float,
            int,
            int,
            tuple[tuple[str, str, float], ...],
        ]
    ] = []
    for alias in words:
        prompt = codec.action_alias_prompt_symbols(alias)
        correct, total = law.sequence_accuracy(state, prompt)
        if total == 0 or correct < total - 1:
            continue
        cue = sense_grounded_symbols(
            law,
            law.reset_context(state),
            prompt,
        )
        action_work = tuple(
            (
                alias,
                action_id,
                law.candidate_sequence_work(
                    cue,
                    codec.grounded.action_symbols(action_id),
                )[0],
            )
            for action_id in GROUND_ACTIONS
        )
        ranked = sorted(action_work, key=lambda row: (-row[2], row[1]))
        runner_up_work = ranked[1][2]
        margin = ranked[0][2] - runner_up_work
        required = max(1.0e-6, 1.0e-6 * abs(ranked[0][2]))
        if ranked[0][2] <= 0.0 or margin <= required:
            raise CassiDiscourseLanguageError("ambiguous_action")
        resolved.append(
            (
                alias,
                ranked[0][1],
                correct / total,
                ranked[0][2],
                correct,
                total,
                action_work,
            )
        )
    if not resolved:
        return None
    actions = {row[1] for row in resolved}
    if len(actions) != 1:
        raise CassiDiscourseLanguageError("ambiguous_action")
    winner = min(resolved, key=lambda row: (-row[3], row[0]))
    return CassiActionAliasDecision(
        alias=winner[0],
        action_id=winner[1],
        cue_accuracy=winner[2],
        cue_correct=winner[4],
        cue_total=winner[5],
        field_work=winner[3],
        candidate_work=tuple(
            candidate
            for row in resolved
            for candidate in row[6]
        ),
    )


def parse_relation_family(text: str) -> str:
    families = tuple(
        family
        for family, pattern in _RELATION_FAMILY_PATTERNS
        if pattern.search(text)
    )
    if len(families) != 1:
        raise CassiDiscourseLanguageError("ambiguous_relation_family")
    return families[0]


def parse_action_candidates(text: str) -> tuple[str, ...]:
    return tuple(
        action_id
        for action_id, pattern in _ACTION_SLOT_PATTERNS
        if pattern.search(text)
    )


def parse_action_clause(text: str) -> str:
    matches = parse_action_candidates(text)
    if len(matches) != 1:
        raise CassiDiscourseLanguageError("action slot is unresolved or ambiguous")
    return matches[0]


def parse_action_alias_surface(text: str) -> str:
    for pattern in _ACTION_ALIAS_PATTERNS:
        match = pattern.search(text)
        if match is not None:
            return match.group("alias").casefold()
    raise CassiDiscourseLanguageError("action alias surface is unresolved")
def parse_order_presentation(text: str) -> str:
    return (
        "reverse"
        if re.search(
            r"\breverse\b|\bsecond\b.*\bfirst\b|\blater\b.*\bearlier\b",
            text,
            re.IGNORECASE,
        )
        else "forward"
    )


def split_goal_action_clauses(text: str) -> tuple[str, str, str]:
    pieces = tuple(
        piece.strip(" .")
        for piece in re.split(r"\bthen\b|[,;:]", text, flags=re.IGNORECASE)
        if piece.strip(" .")
    )
    if len(pieces) < 3:
        raise CassiDiscourseLanguageError("deferred goal does not contain three clauses")
    return pieces[-3], pieces[-2], pieces[-1]
def frame_surface_candidates(text: str) -> dict[str, str]:
    candidates: dict[str, str] = {}
    lowered = f" {text.casefold()} "
    if " it " in lowered:
        candidates["surface.active"] = "it"
    aliases = tuple(match.group(0) for match in _ROUTE_ALIAS_PATTERN.finditer(text))
    for index, alias in enumerate(aliases[:2], start=1):
        candidates[f"surface.alias-{index}"] = alias
    for color in ("red", "blue", "green"):
        if re.search(rf"\b{color}\b", text, re.IGNORECASE):
            candidates[f"surface.{color}"] = color
    if "unnamed object" in lowered:
        candidates["surface.unnamed"] = "unnamed object"
    return candidates


def _frame_surface_slot(text: str, surface: str) -> str:
    folded = surface.casefold()
    if folded == "it":
        return "surface.active"
    if folded == "unnamed object":
        return "surface.unnamed"
    if folded in {"red", "blue", "green"}:
        return f"surface.{folded}"
    for slot, candidate in frame_surface_candidates(text).items():
        if candidate.casefold() == folded:
            return slot
    raise CassiDiscourseLanguageError("semantic frame surface is unresolved")


def semantic_frame_target(
    text: str,
    route_id: str,
    *,
    clarification: str | None = None,
) -> CassiDiscourseFrameTarget:
    commit = route_id in {
        "route.action",
        "route.action-alias-binding",
        "route.binding",
        "route.goal-declaration",
        "route.goal-trigger",
    }
    action_id = None
    family_id = None
    binding_reference = None
    subject_slot = None
    comparison_slot = None
    presentation = None
    if route_id in {
        "route.action",
        "route.action-alias-binding",
        "route.prediction",
    }:
        action_id = parse_action_clause(text)
    elif route_id in {"route.spatial", "route.reference"}:
        family_id = parse_relation_family(text)
        if route_id == "route.reference":
            subject, comparison = parse_reference_query(text)
            subject_slot = _frame_surface_slot(text, subject)
            comparison_slot = _frame_surface_slot(text, comparison)
    elif route_id == "route.binding":
        name, binding_reference = parse_binding(text)
        subject_slot = _frame_surface_slot(text, name)
    elif route_id == "route.ordering":
        presentation = parse_order_presentation(text)
    return CassiDiscourseFrameTarget(
        route_id=route_id,
        commit=commit,
        action_id=action_id,
        family_id=family_id,
        binding_reference=binding_reference,
        subject_slot=subject_slot,
        comparison_slot=comparison_slot,
        presentation=presentation,
        clarification=(clarification or "unsupported")
        if route_id == "route.abstain"
        else None,
    )




def consolidate_deferred_goal(
    law: CassiQiTrajectoryLaw,
    codec: CassiDiscourseEventCodec,
    state: QiFieldState,
    actions: Sequence[str],
) -> tuple[QiFieldState, int]:
    registers = law.read_live_boundary_values(state, FIELD_LIVE_REGISTER_SIZE)
    episode = codec.goal_episode_symbols(actions)
    candidate = law.learn_sequence(state, episode, strength=1.0)
    candidate = law.write_live_boundary_values(candidate, registers)
    return candidate, len(episode)


def select_deferred_goal(
    controller: QiFieldController,
    law: CassiQiTrajectoryLaw,
    codec: CassiDiscourseEventCodec,
    state: QiFieldState,
) -> CassiDeferredGoalDecision:
    cue = sense_grounded_symbols(
        law,
        law.reset_context(state),
        codec.goal_prompt_symbols(),
    )
    rows: list[tuple[tuple[str, str, str], float]] = []
    for first, second, third in itertools.product(GROUND_ACTIONS, repeat=3):
        actions = (first, second, third)
        score, _ = law.candidate_sequence_work(cue, codec.goal_plan_symbols(actions))
        rows.append((actions, score))
    ranked = sorted(rows, key=lambda item: (-item[1], item[0]))
    winner, runner_up = ranked[0], ranked[1]
    margin = winner[1] - runner_up[1]
    required = max(1.0e-6, 1.0e-6 * abs(winner[1]))
    if winner[1] <= 0.0 or margin <= required:
        raise CassiDiscourseLanguageError("deferred goal did not resolve a unique plan")
    return CassiDeferredGoalDecision(
        actions=winner[0],
        goal_work=winner[1],
        runner_up_work=runner_up[1],
        margin=margin,
        candidate_count=len(rows),
        state_sha256=qi_state_sha256(controller, cue),
        trained_memory_sha256=law.memory_sha256(cue),
    )


__all__ = [
    "CassiActionAliasDecision",
    "CassiDeferredGoalDecision",
    "CassiDiscourseFrameDecision",
    "CassiDiscourseFrameSlotDecision",
    "CassiDiscourseFrameTarget",
    "CassiDiscourseEventCodec",
    "CassiDiscourseLanguageError",
    "DISCOURSE_ABSTAIN_CLARIFICATIONS",
    "DISCOURSE_FRAME_SCHEMA",
    "DISCOURSE_FRAME_MINIMUM_HISTORY",
    "DISCOURSE_GOAL_SCHEMA",
    "DISCOURSE_ROUTES",
    "DISCOURSE_ROUTE_TRAINING_PROMPTS",
    "DISCOURSE_ROUTE_VALIDATION_PROMPTS",
    "consolidate_deferred_goal",
    "frame_surface_candidates",
    "parse_binding",
    "parse_action_alias_surface",
    "parse_order_presentation",
    "parse_reference_query",
    "parse_relation_family",
    "select_deferred_goal",
    "parse_action_candidates",
    "parse_action_clause",
    "select_action_alias",
    "select_discourse_frame",
    "semantic_frame_target",
    "split_goal_action_clauses",
]
