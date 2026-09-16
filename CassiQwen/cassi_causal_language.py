"""Fixed UTF-8 language boundary for the field-owned causal learner.

This module contributes framing and deterministic world ground truth only.  It
contains no learned lexicon, embedding, vocabulary matrix, transition table, or
adaptive state.  Acquired relations live exclusively in
``CausalEventLearner.state.field``.
"""
from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass
from typing import Any, Callable, Final, Mapping, Sequence

from cassi_causal_event_field import CausalEventLearner, CausalProfile
from cassi_raw_event_field import (
    AcquisitionProfile,
    canonical_packet,
    decode_packet,
    encode_packet,
)


BOUNDARY_SCHEMA: Final[str] = "cassi.causal-language-boundary.v2"
WORLD_SCHEMA: Final[str] = "cassi.causal-language-world.v1"
_MAX_ORDERED_UTF8_BYTES: Final[int] = 8
_ORDERED_SEQUENCE_BYTES: Final[int] = 7
_SAFE_LEXEMES: Final[tuple[str, ...]] = tuple(
    chr(value) for value in range(ord("a"), ord("z") + 1)
)


class CausalLanguageError(RuntimeError):
    """The fixed language boundary or deterministic world is invalid."""


def _canonical_json(value: Mapping[str, Any]) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def _sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(value)).hexdigest()


def _lexeme(name: str, value: str) -> bytes:
    if not isinstance(value, str) or len(value) != 1 or value not in _SAFE_LEXEMES:
        raise CausalLanguageError(f"{name} must be one fixed lowercase ASCII lexeme")
    return value.encode("utf-8", "strict")


def text_packet(text: str) -> bytes:
    """Encode one raw ordered UTF-8 span without normalization."""

    if not isinstance(text, str) or not text:
        raise CausalLanguageError("text must be nonempty")
    try:
        raw = text.encode("utf-8", "strict")
    except UnicodeEncodeError as error:
        raise CausalLanguageError(f"text is not valid UTF-8: {error}") from error
    if len(raw) > _MAX_ORDERED_UTF8_BYTES:
        raise CausalLanguageError(
            f"ordered UTF-8 span exceeds {_MAX_ORDERED_UTF8_BYTES} bytes"
        )
    return encode_packet((raw,))


def ordered_expression(subject: str, relation: str, object_: str) -> bytes:
    """Encode three ordered UTF-8 events plus an explicit end-expression marker."""

    subject_raw = _lexeme("subject", subject)
    relation_raw = _lexeme("relation", relation)
    object_raw = _lexeme("object", object_)
    sequence = b"<" + subject_raw + b"|" + relation_raw + b"|" + object_raw + b">"
    if len(sequence) != _ORDERED_SEQUENCE_BYTES:
        raise CausalLanguageError("ordered event sequence has invalid width")
    return encode_packet((sequence,))


def decode_ordered_expression(packet: bytes) -> tuple[str, str, str]:
    """Parse the fixed sequence without canonical span sorting."""

    spans = decode_packet(packet)
    if len(spans) != 1:
        raise CausalLanguageError("ordered expression must contain exactly one sequence")
    sequence = spans[0]
    if (
        len(sequence) != _ORDERED_SEQUENCE_BYTES
        or sequence[0:1] != b"<"
        or sequence[2:3] != b"|"
        or sequence[4:5] != b"|"
        or sequence[6:7] != b">"
    ):
        raise CausalLanguageError("ordered expression framing is invalid")
    try:
        values: tuple[str, str, str] = (
            sequence[1:2].decode("utf-8", "strict"),
            sequence[3:4].decode("utf-8", "strict"),
            sequence[5:6].decode("utf-8", "strict"),
        )
    except UnicodeDecodeError as error:
        raise CausalLanguageError(f"ordered expression is not valid UTF-8: {error}") from error
    for name, value in zip(("subject", "relation", "object"), values, strict=True):
        _lexeme(name, value)
    return values


def role_marked_expression(subject: str, relation: str, object_: str) -> bytes:
    """Encode explicit roles as an unordered-span diagnostic, not syntax."""

    subject_raw = _lexeme("subject", subject)
    relation_raw = _lexeme("relation", relation)
    object_raw = _lexeme("object", object_)
    return encode_packet((b"S" + subject_raw, b"R" + relation_raw, b"O" + object_raw))


def lexical_command(construction: str, entity: str) -> bytes:
    """Encode a construction and entity with fixed explicit slot markers."""

    construction_raw = _lexeme("construction", construction)
    entity_raw = _lexeme("entity", entity)
    return encode_packet((b"V" + construction_raw, b"E" + entity_raw))


def grounded_state(state: str, entity: str) -> bytes:
    state_raw = _lexeme("state", state)
    entity_raw = _lexeme("entity", entity)
    return encode_packet((b"Q" + state_raw, b"E" + entity_raw))


def action_packet(action: str) -> bytes:
    return encode_packet((b"A" + _lexeme("action", action),))


def outcome_packet(outcome: str) -> bytes:
    return encode_packet((b"Z" + _lexeme("outcome", outcome),))


def language_profile() -> CausalProfile:
    """Return the fixed profile used by the language campaign."""

    return CausalProfile(
        acquisition=AcquisitionProfile(wave_width=4096, payload_limit=16),
        policy="mismatch-gated",
        max_actions=16,
        max_depth=3,
        max_expansions=64,
        key_channels=8,
    )


@dataclass(frozen=True, slots=True)
class CausalLanguageWorld:
    """Immutable randomized world truth; never a learner memory or router."""

    seed: int
    entity_seen: str
    entity_held: str
    entity_other: str
    move_word: str
    move_paraphrase: str
    inspect_word: str
    unknown_word: str
    move_action: str
    inspect_action: str
    distractor_action: str
    alternate_action: str
    moved_state: str
    inspected_state: str
    failure_state: str
    ordered_subject: str
    ordered_object: str
    ordered_relation: str
    ordered_forward_action: str
    ordered_reverse_action: str
    ordered_goal: str
    schema: str = WORLD_SCHEMA

    @classmethod
    def randomized(cls, seed: int) -> "CausalLanguageWorld":
        if isinstance(seed, bool) or not isinstance(seed, int):
            raise CausalLanguageError("seed must be an integer")
        rng = random.Random(seed ^ 0x1A69_2026)
        values = rng.sample(_SAFE_LEXEMES, 20)
        return cls(seed, *values)

    def __post_init__(self) -> None:
        if self.schema != WORLD_SCHEMA:
            raise CausalLanguageError("language world schema mismatch")
        values = [
            value
            for name, value in self.as_dict().items()
            if name not in {"schema", "seed"}
        ]
        if len(set(values)) != len(values):
            raise CausalLanguageError("language world lexemes must be distinct")
        for index, value in enumerate(values):
            _lexeme(f"world lexeme {index}", value)

    @property
    def actions(self) -> tuple[bytes, ...]:
        return tuple(
            action_packet(value)
            for value in (
                self.move_action,
                self.inspect_action,
                self.distractor_action,
                self.alternate_action,
            )
        )

    @property
    def fingerprint(self) -> str:
        return _sha256(self.as_dict())

    def as_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "seed": self.seed,
            "entity_seen": self.entity_seen,
            "entity_held": self.entity_held,
            "entity_other": self.entity_other,
            "move_word": self.move_word,
            "move_paraphrase": self.move_paraphrase,
            "inspect_word": self.inspect_word,
            "unknown_word": self.unknown_word,
            "move_action": self.move_action,
            "inspect_action": self.inspect_action,
            "distractor_action": self.distractor_action,
            "alternate_action": self.alternate_action,
            "moved_state": self.moved_state,
            "inspected_state": self.inspected_state,
            "failure_state": self.failure_state,
            "ordered_subject": self.ordered_subject,
            "ordered_object": self.ordered_object,
            "ordered_relation": self.ordered_relation,
            "ordered_forward_action": self.ordered_forward_action,
            "ordered_reverse_action": self.ordered_reverse_action,
            "ordered_goal": self.ordered_goal,
        }

    def command(self, construction: str, entity: str) -> bytes:
        return lexical_command(construction, entity)

    def task_goal(self, entity: str) -> bytes:
        """Return the predeclared success state, independent of construction."""

        return grounded_state(self.moved_state, entity)

    def correct_action(self, construction: str) -> bytes:
        if construction in {self.move_word, self.move_paraphrase}:
            return action_packet(self.move_action)
        if construction == self.inspect_word:
            return action_packet(self.inspect_action)
        raise CausalLanguageError("world has no correct action for construction")

    def unknown_consequence(self, entity: str, action: bytes) -> bytes:
        """Return deterministic failure after an unknown command commits."""

        canonical_packet(action)
        return grounded_state(self.failure_state, entity)

    def consequence(self, construction: str, entity: str, action: bytes) -> bytes:
        """Return feedback after commitment; task success is construction-independent."""

        if construction == self.unknown_word:
            return self.unknown_consequence(entity, action)
        if canonical_packet(action) == canonical_packet(self.correct_action(construction)):
            return self.task_goal(entity)
        return grounded_state(self.failure_state, entity)

    def compound_command(
        self, first_construction: str, second_construction: str, entity: str
    ) -> bytes:
        """Compose a commutative multiset of two grounded construction spans."""

        first = _lexeme("first construction", first_construction)
        second = _lexeme("second construction", second_construction)
        entity_raw = _lexeme("entity", entity)
        return encode_packet((b"V" + first, b"V" + second, b"E" + entity_raw))

    def compound_goal(self, entity: str) -> bytes:
        """Require two generic successes; it does not identify either action."""

        entity_raw = _lexeme("entity", entity)
        success = b"Q" + _lexeme("success state", self.moved_state)
        return encode_packet((success, success, b"E" + entity_raw))

    def compound_consequence(self, observation: bytes, action: bytes) -> bytes:
        """Apply one grounded construction after the action has been committed."""

        spans = list(decode_packet(canonical_packet(observation)))
        action_value = canonical_packet(action)
        replacements: tuple[str, ...]
        if action_value == canonical_packet(action_packet(self.move_action)):
            replacements = (self.move_word, self.move_paraphrase)
        elif action_value == canonical_packet(action_packet(self.inspect_action)):
            replacements = (self.inspect_word,)
        else:
            return grounded_state(self.failure_state, self.entity_other)
        for construction in replacements:
            marker = b"V" + _lexeme("construction", construction)
            if marker in spans:
                spans.remove(marker)
                spans.append(b"Q" + _lexeme("success state", self.moved_state))
                return encode_packet(tuple(spans))
        return grounded_state(self.failure_state, self.entity_other)

    def clarification_consequence(self, revealed: bytes, action: bytes) -> bytes:
        """Evaluate one revealed branch only after its repair action commits."""

        revealed_value = canonical_packet(revealed)
        if revealed_value == canonical_packet(
            self.command(self.move_word, self.entity_seen)
        ):
            expected = self.correct_action(self.move_word)
        elif revealed_value == canonical_packet(
            self.command(self.inspect_word, self.entity_held)
        ):
            expected = self.correct_action(self.inspect_word)
        else:
            return self.ordered_failure
        if canonical_packet(action) == canonical_packet(expected):
            return self.ordered_target
        return self.ordered_failure


    def ordered_observation(self, *, reversed_arguments: bool) -> bytes:
        subject = self.ordered_object if reversed_arguments else self.ordered_subject
        object_ = self.ordered_subject if reversed_arguments else self.ordered_object
        return ordered_expression(subject, self.ordered_relation, object_)

    def ordered_correct_action(self, *, reversed_arguments: bool) -> bytes:
        return action_packet(
            self.ordered_reverse_action if reversed_arguments else self.ordered_forward_action
        )

    @property
    def ordered_target(self) -> bytes:
        return outcome_packet(self.ordered_goal)

    @property
    def ordered_failure(self) -> bytes:
        return grounded_state(self.failure_state, self.entity_other)

    def ordered_consequence(self, observation: bytes, action: bytes) -> bytes:
        """Parse the committed observation, then evaluate its action."""

        subject, relation, object_ = decode_ordered_expression(observation)
        if relation != self.ordered_relation:
            return self.ordered_failure
        if (subject, object_) == (self.ordered_subject, self.ordered_object):
            reversed_arguments = False
        elif (subject, object_) == (self.ordered_object, self.ordered_subject):
            reversed_arguments = True
        else:
            return self.ordered_failure
        if canonical_packet(action) == canonical_packet(
            self.ordered_correct_action(reversed_arguments=reversed_arguments)
        ):
            return self.ordered_target
        return self.ordered_failure


def committed_action(decision: Mapping[str, Any]) -> bytes:
    value = decision.get("action_hex")
    if not isinstance(value, str):
        raise CausalLanguageError("decision did not commit an action")
    try:
        action = bytes.fromhex(value)
        return canonical_packet(action)
    except (ValueError, TypeError) as error:
        raise CausalLanguageError("decision action is invalid") from error


def choose_and_observe(
    learner: CausalEventLearner,
    *,
    observation: bytes,
    actions: Sequence[bytes],
    goal: bytes,
    consequence: Callable[[bytes], bytes],
    learn: bool,
) -> tuple[dict[str, Any], dict[str, Any], bytes]:
    """Run one closed-loop episode; consequence is consulted after commitment."""

    learner.reset()
    learner.observe(observation, learn=False)
    decision = learner.decide(actions, goal)
    action = committed_action(decision)
    outcome = consequence(action)
    admission = learner.observe(outcome, learn=learn)
    return decision, admission, outcome


__all__ = [
    "BOUNDARY_SCHEMA",
    "CausalLanguageError",
    "CausalLanguageWorld",
    "action_packet",
    "choose_and_observe",
    "committed_action",
    "decode_ordered_expression",
    "grounded_state",
    "language_profile",
    "lexical_command",
    "ordered_expression",
    "outcome_packet",
    "role_marked_expression",
    "text_packet",
]
