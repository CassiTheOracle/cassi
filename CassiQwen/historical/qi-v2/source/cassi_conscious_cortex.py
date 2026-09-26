"""Provenance-safe candidate scorer for the conscious core.

``CassiConsciousCortex`` is a read-only candidate-evaluation boundary over one
single-lane conscious field.  ``rank_candidates`` is the sole ranking entrypoint:
caller-provided candidate bytes are canonicalized, de-duplicated, and scored on
isolated conscious-field branches.  The supplied root state is never mutated and
the adapter never contacts a model server, generates tokens, or turns candidate
material into an observation, memory, action, commitment, or truth.

Each candidate is represented by exactly one
``TEACHER_PROPOSAL / EXTERNAL_PROPOSAL / TEACHER`` event whose source ID binds
it to the exact source identity and SHA-256 passed at construction.  The returned
ranking is deterministic: payloads are canonicalized before sequence assignment,
scores use the conscious field's stable interoceptive layout, and equal scores
are ordered by the canonical event ID.  The adapter has no server, tokenizer,
generation, persistence, or adaptive state API.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass
from typing import Any, Iterable, Sequence

import torch

from cassi_conscious_field import (
    BOUNDARY_PROFILE_ID,
    CONSCIOUS_FIELD_PROFILE_ID,
    INTEROCEPTIVE_LAYOUT_ID,
    CassiConsciousBranch,
    CassiConsciousField,
    CassiConsciousFieldError,
    ConsciousAccess,
    InteroceptiveValueReadout,
    MetacognitiveReadout,
    tensor_wave_sha256,
)
from cassi_conscious_protocol import (
    ActorClass,
    CassiExperienceEvent,
    EventKind,
    MAX_PAYLOAD_BYTES,
    RealityStatus,
    create_event,
)
from cassi_qi_field import (
    QI_CODEBOOK_PROFILE_ID,
    QI_FIELD_CONFIG_SCHEMA,
    QI_FIELD_LAYOUT_ID,
    QI_FIELD_OPERATOR_PROFILE_ID,
    QI_FIELD_STATE_SCHEMA,
    QiFieldState,
)


CORTEX_PROFILE_ID = "cassi.conscious.cortex.v2"
CORTEX_SCHEMA = "cassi.conscious.cortex.v2"
DEFAULT_MAX_CANDIDATE_BYTES = MAX_PAYLOAD_BYTES
DEFAULT_MAX_CANDIDATE_COUNT = 32
MAX_CANDIDATE_COUNT = 32
MAX_IMAGINATION_STEPS = 64
_SHA256_RE = re.compile(r"[0-9a-f]{64}\Z")


class CassiConsciousCortexError(ValueError):
    """Raised when a candidate or cortex boundary value is invalid."""


def _digest(name: str, value: object, *, allow_empty: bool = False) -> str:
    """Validate and return one exact lower-case SHA-256 digest."""

    if not isinstance(value, str):
        raise CassiConsciousCortexError(f"{name} must be a lower-case SHA-256 digest")
    if value == "" and allow_empty:
        return value
    if _SHA256_RE.fullmatch(value) is None:
        raise CassiConsciousCortexError(f"{name} must be a lower-case SHA-256 digest")
    return value


def _sequence_start(value: object) -> int:
    """Validate a non-negative integer sequence start without accepting bool."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise CassiConsciousCortexError("sequence_start must be a non-negative integer")
    return value


def _positive_int(name: str, value: object, *, maximum: int | None = None) -> int:
    """Validate a bounded positive integer without accepting bool."""

    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise CassiConsciousCortexError(f"{name} must be a positive integer")
    if maximum is not None and value > maximum:
        raise CassiConsciousCortexError(f"{name} must not exceed {maximum}")
    return value


def _finite(value: object, *, name: str) -> float:
    """Return a finite float for immutable result validation."""

    try:
        converted = float(value)
    except (TypeError, ValueError) as exc:
        raise CassiConsciousCortexError(f"{name} must be finite") from exc
    if not math.isfinite(converted):
        raise CassiConsciousCortexError(f"{name} must be finite")
    return converted


def _field_digest(state: QiFieldState) -> str:
    """Hash the exact sole adaptive field tensor for a root receipt."""

    return tensor_wave_sha256(state.field)


def _candidate_payload(candidate: object, *, maximum_bytes: int) -> tuple[bytes, str]:
    """Normalize one already-generated UTF-8 candidate without generation."""

    if isinstance(candidate, str):
        try:
            payload = candidate.encode("utf-8", errors="strict")
        except UnicodeError as exc:
            raise CassiConsciousCortexError("candidate text is not valid UTF-8") from exc
    elif isinstance(candidate, bytes):
        payload = candidate
    else:
        raise CassiConsciousCortexError("candidate must be UTF-8 text or bytes")

    if not payload:
        raise CassiConsciousCortexError("candidate payload must be non-empty")
    if len(payload) > maximum_bytes:
        raise CassiConsciousCortexError("candidate payload is oversized")
    try:
        text = payload.decode("utf-8", errors="strict")
    except UnicodeError as exc:
        raise CassiConsciousCortexError("candidate bytes are not valid UTF-8") from exc
    if not text:
        # This is reachable for no ordinary valid non-empty UTF-8 payload, but
        # keeps the adapter invariant explicit for unusual decoder behavior.
        raise CassiConsciousCortexError("candidate text must be non-empty")
    return payload, text


@dataclass(frozen=True)
class CortexCandidateResult:
    """One immutable external-teacher candidate, branch, and functional score."""

    payload: bytes
    text: str
    event: CassiExperienceEvent
    branch: CassiConsciousBranch
    interoception: InteroceptiveValueReadout
    metacognition: MetacognitiveReadout
    score: float

    def __post_init__(self) -> None:
        if not isinstance(self.payload, bytes) or not self.payload:
            raise CassiConsciousCortexError("result payload must be non-empty bytes")
        if not isinstance(self.text, str) or not self.text:
            raise CassiConsciousCortexError("result text must be non-empty text")
        try:
            if self.text.encode("utf-8") != self.payload:
                raise CassiConsciousCortexError("result text/payload mismatch")
        except UnicodeError as exc:
            raise CassiConsciousCortexError("result text is not valid UTF-8") from exc
        if not isinstance(self.event, CassiExperienceEvent):
            raise CassiConsciousCortexError("result event is invalid")
        if self.event.kind is not EventKind.TEACHER_PROPOSAL:
            raise CassiConsciousCortexError("result event must be a teacher proposal")
        if self.event.reality_status is not RealityStatus.EXTERNAL_PROPOSAL:
            raise CassiConsciousCortexError("result event must be an external proposal")
        if self.event.actor is not ActorClass.TEACHER:
            raise CassiConsciousCortexError("result event must be authored by the teacher")
        if not isinstance(self.branch, CassiConsciousBranch):
            raise CassiConsciousCortexError("result branch is invalid")
        if not isinstance(self.interoception, InteroceptiveValueReadout):
            raise CassiConsciousCortexError("result interoception is invalid")
        if not isinstance(self.metacognition, MetacognitiveReadout):
            raise CassiConsciousCortexError("result metacognition is invalid")
        object.__setattr__(self, "score", _finite(self.score, name="candidate score"))

    @property
    def value(self) -> InteroceptiveValueReadout:
        """Compatibility alias for the field's candidate-value terminology."""

        return self.interoception

    @property
    def candidate_sha256(self) -> str:
        """SHA-256 of the exact candidate payload bytes."""

        return hashlib.sha256(self.payload).hexdigest()

    @property
    def event_id(self) -> str:
        """Canonical immutable event identity."""

        return self.event.event_id

    @property
    def branch_id(self) -> str:
        """Canonical isolated-branch identity."""

        return self.branch.branch_id


@dataclass(frozen=True)
class CortexRanking:
    """Immutable deterministic ranking of external-teacher candidates."""

    ranked: tuple[CortexCandidateResult, ...]
    root_field_sha256: str
    sequence_start: int
    next_sequence: int
    source_id: str
    source_sha256: str
    profile_id: str = CORTEX_PROFILE_ID

    def __post_init__(self) -> None:
        if not self.ranked:
            raise CassiConsciousCortexError("ranking must contain at least one candidate")
        if not isinstance(self.ranked, tuple) or any(
            not isinstance(candidate, CortexCandidateResult) for candidate in self.ranked
        ):
            raise CassiConsciousCortexError("ranking candidates must be an immutable tuple")
        if not isinstance(self.source_id, str) or not self.source_id:
            raise CassiConsciousCortexError("ranking source_id must be non-empty text")
        _digest("root_field_sha256", self.root_field_sha256)
        _digest("source_sha256", self.source_sha256)
        if self.profile_id != CORTEX_PROFILE_ID:
            raise CassiConsciousCortexError("ranking profile identity mismatch")
        start = _sequence_start(self.sequence_start)
        expected_next = start + len(self.ranked)
        if self.next_sequence != expected_next:
            raise CassiConsciousCortexError("ranking next_sequence is not monotonic")
        previous_key: tuple[float, str] | None = None
        for candidate in self.ranked:
            if candidate.event.source_id != self.source_id:
                raise CassiConsciousCortexError("candidate event source ID mismatch")
            if candidate.branch.root_field_sha256 != self.root_field_sha256:
                raise CassiConsciousCortexError("candidate branch root mismatch")
            key = (-candidate.score, candidate.event.event_id)
            if previous_key is not None and key < previous_key:
                raise CassiConsciousCortexError("ranking is not canonical")
            previous_key = key

    @property
    def results(self) -> tuple[CortexCandidateResult, ...]:
        """Alias for callers that prefer the generic result name."""

        return self.ranked

    @property
    def winner(self) -> CortexCandidateResult:
        """Highest-scoring result, with event-ID tie break already applied."""

        return self.ranked[0]

    @property
    def winning_payload(self) -> bytes:
        """Payload selected by the deterministic ranking."""

        return self.winner.payload

    def __iter__(self) -> Iterable[CortexCandidateResult]:
        return iter(self.ranked)

    def __len__(self) -> int:
        return len(self.ranked)


class CassiConsciousCortex:
    """Read-only candidate scorer over one single-lane conscious field.

    Candidates are external-teacher material: proposals, never observations,
    memories, actions, commitments, or truth.  The adapter does not own a live
    state and never calls a server or token generator.  ``rank_candidates``
    evaluates caller-provided candidate bytes on isolated branches and leaves the
    supplied root state bit-identical.
    """

    def __init__(
        self,
        field: CassiConsciousField,
        source_id: str,
        source_sha256: str,
        *,
        max_candidate_bytes: int = DEFAULT_MAX_CANDIDATE_BYTES,
        max_candidate_count: int = DEFAULT_MAX_CANDIDATE_COUNT,
    ) -> None:
        if not isinstance(field, CassiConsciousField):
            raise CassiConsciousCortexError("field must be a CassiConsciousField")
        if not isinstance(source_id, str) or not source_id:
            raise CassiConsciousCortexError("source_id must be non-empty text")
        self._source_id = source_id
        self._source_sha256 = _digest("source_sha256", source_sha256)
        if (
            isinstance(max_candidate_bytes, bool)
            or not isinstance(max_candidate_bytes, int)
            or max_candidate_bytes < 1
            or max_candidate_bytes > MAX_PAYLOAD_BYTES
        ):
            raise CassiConsciousCortexError(
                f"max_candidate_bytes must be in 1..{MAX_PAYLOAD_BYTES}"
            )
        self._max_candidate_bytes = max_candidate_bytes
        self._max_candidate_count = _positive_int(
            "max_candidate_count", max_candidate_count, maximum=MAX_CANDIDATE_COUNT
        )
        self._field = field

    @property
    def conscious_field(self) -> CassiConsciousField:
        """The fixed field controller used for read-only branch/readout calls."""

        return self._field

    @property
    def source_id(self) -> str:
        """Exact non-empty source identity pinned alongside the SHA-256."""

        return self._source_id

    @property
    def source_sha256(self) -> str:
        """Exact lower-case SHA-256 identity of the pinned source."""

        return self._source_sha256

    @property
    def max_candidate_bytes(self) -> int:
        """Maximum UTF-8 payload size admitted by this adapter."""

        return self._max_candidate_bytes

    @property
    def max_candidate_count(self) -> int:
        """Maximum candidate count admitted by this adapter."""

        return self._max_candidate_count

    def _validate_state(self, state: object) -> QiFieldState:
        """Validate ownership and enforce the single-lane boundary."""

        if not isinstance(state, QiFieldState):
            raise CassiConsciousCortexError("state must be a QiFieldState")
        try:
            if state.batch_size != 1:
                raise CassiConsciousCortexError("cortex adapter accepts only a single-lane state")
        except CassiConsciousCortexError:
            raise
        except Exception as exc:
            raise CassiConsciousCortexError("invalid Qi field state") from exc
        try:
            # The public field readout validates shape, device, dtype, and
            # finiteness against this controller without mutating the state.
            self._field.access_gate(state)
        except (CassiConsciousFieldError, ValueError) as exc:
            raise CassiConsciousCortexError(str(exc)) from exc
        return state

    @staticmethod
    def _score(value: InteroceptiveValueReadout) -> float:
        """Use the field's stable candidate-value score, with uncertainty inverted."""

        score = (
            value.energy_safety
            + value.coherence
            + value.access
            + value.slow_continuity
            + 1.0
            - value.uncertainty
        ) / 5.0
        return max(0.0, min(1.0, _finite(score, name="candidate score")))

    def _normalize_candidates(
        self,
        candidates: Sequence[bytes | str],
    ) -> list[tuple[bytes, str]]:
        """Normalize, bound, de-duplicate, and canonically sort candidates."""

        if isinstance(candidates, (str, bytes, bytearray)) or not isinstance(candidates, Sequence):
            raise CassiConsciousCortexError("candidates must be a non-empty sequence")
        if not candidates:
            raise CassiConsciousCortexError("at least one candidate is required")
        if len(candidates) > self._max_candidate_count:
            raise CassiConsciousCortexError("candidate count exceeds configured maximum")
        normalized = [
            _candidate_payload(candidate, maximum_bytes=self._max_candidate_bytes)
            for candidate in candidates
        ]
        payloads = [payload for payload, _ in normalized]
        if len(set(payloads)) != len(payloads):
            raise CassiConsciousCortexError("duplicate candidate payloads are not permitted")
        return sorted(normalized, key=lambda item: item[0])

    def _rank_normalized(
        self,
        state: QiFieldState,
        normalized: Sequence[tuple[bytes, str]],
        *,
        sequence_start: int,
        parent_event_id: str,
        steps: int,
    ) -> CortexRanking:
        """Rank validated canonical candidates on isolated branches."""

        validated_state = self._validate_state(state)
        root_digest = _field_digest(validated_state)
        scored: list[CortexCandidateResult] = []
        for offset, (payload, text) in enumerate(normalized):
            event = create_event(
                sequence=sequence_start + offset,
                kind=EventKind.TEACHER_PROPOSAL,
                reality_status=RealityStatus.EXTERNAL_PROPOSAL,
                actor=ActorClass.TEACHER,
                payload=payload,
                source_id=self.source_id,
                parent_event_id=parent_event_id,
            )
            try:
                branch = self._field.accept_teacher_proposal(
                    validated_state,
                    event,
                    root_event_id=parent_event_id,
                    steps=steps,
                )
                value = self._field.interoception(branch.state, prior_state=validated_state)
                metacognition = self._field.metacognition(branch.state, event=event)
            except (CassiConsciousFieldError, ValueError) as exc:
                raise CassiConsciousCortexError(str(exc)) from exc
            scored.append(
                CortexCandidateResult(
                    payload=payload,
                    text=text,
                    event=event,
                    branch=branch,
                    interoception=value,
                    metacognition=metacognition,
                    score=self._score(value),
                )
            )
        ranked = tuple(sorted(scored, key=lambda result: (-result.score, result.event.event_id)))
        # Re-check the root after all branch work.  This is a receipt-level
        # guard that also makes the no-mutation contract explicit.
        if _field_digest(validated_state) != root_digest:
            raise CassiConsciousCortexError("live root Qi state changed during candidate ranking")
        return CortexRanking(
            ranked=ranked,
            root_field_sha256=root_digest,
            sequence_start=sequence_start,
            next_sequence=sequence_start + len(ranked),
            source_id=self.source_id,
            source_sha256=self.source_sha256,
        )

    def rank_candidates(
        self,
        state: QiFieldState,
        candidates: Sequence[bytes | str],
        *,
        sequence_start: int,
        parent_event_id: str = "",
        steps: int = 1,
    ) -> CortexRanking:
        """Rank generic caller-provided external-teacher candidates."""

        start = _sequence_start(sequence_start)
        parent = _digest("parent_event_id", parent_event_id, allow_empty=True)
        branch_steps = _positive_int("steps", steps, maximum=MAX_IMAGINATION_STEPS)
        normalized = self._normalize_candidates(candidates)
        return self._rank_normalized(
            state,
            normalized,
            sequence_start=start,
            parent_event_id=parent,
            steps=branch_steps,
        )

    def render_context(self, state: QiFieldState) -> dict[str, Any]:
        """Return a finite JSON-safe source/field context without writing state.

        The context contains generic source identity, functional field readouts,
        and exact profile identities only.  It deliberately contains no model
        output, event, memory, action, commitment, or observation claim.
        """

        validated_state = self._validate_state(state)
        access = self._field.access_gate(validated_state)
        condensate = self._field.structural_self(validated_state)
        value = self._field.interoception(validated_state)
        metacognition = self._field.metacognition(validated_state)
        context: dict[str, Any] = {
            "schema": CORTEX_SCHEMA,
            "profile_id": CORTEX_PROFILE_ID,
            "source_id": self.source_id,
            "source_sha256": self.source_sha256,
            "field": {
                "conscious_profile_id": CONSCIOUS_FIELD_PROFILE_ID,
                "boundary_profile_id": BOUNDARY_PROFILE_ID,
                "interoceptive_layout_id": INTEROCEPTIVE_LAYOUT_ID,
                "qi_config_schema": QI_FIELD_CONFIG_SCHEMA,
                "qi_state_schema": QI_FIELD_STATE_SCHEMA,
                "qi_layout_id": QI_FIELD_LAYOUT_ID,
                "qi_operator_profile_id": QI_FIELD_OPERATOR_PROFILE_ID,
                "qi_codebook_profile_id": QI_CODEBOOK_PROFILE_ID,
            },
            "access": {
                "level": access.level.value,
                "granted": bool(access.granted),
                "participating_scales": int(access.participating_scales),
                "cross_scale_coherence": _finite(
                    access.cross_scale_coherence, name="access cross-scale coherence"
                ),
                "uncertainty": _finite(access.uncertainty, name="access uncertainty"),
                "reason": access.reason,
            },
            "self_condensate": {
                "fast_differential": _finite(condensate.fast_differential, name="fast differential"),
                "slow_differential": _finite(condensate.slow_differential, name="slow differential"),
                "velocity_organization": _finite(
                    condensate.velocity_organization, name="velocity organization"
                ),
                "epsilon_stability": _finite(condensate.epsilon_stability, name="epsilon stability"),
                "cross_scale_coherence": _finite(
                    condensate.cross_scale_coherence, name="self cross-scale coherence"
                ),
                "scale_current": _finite(condensate.scale_current, name="scale current"),
                "continuity": _finite(condensate.continuity, name="continuity"),
                "structural_strength": _finite(condensate.structural_strength, name="structural strength"),
                "fingerprint": condensate.fingerprint,
            },
            "interoception": {
                "energy_safety": _finite(value.energy_safety, name="energy safety"),
                "coherence": _finite(value.coherence, name="interoceptive coherence"),
                "access": _finite(value.access, name="interoceptive access"),
                "contradiction_pressure": _finite(
                    value.contradiction_pressure, name="contradiction pressure"
                ),
                "slow_continuity": _finite(value.slow_continuity, name="slow continuity"),
                "controllability_evidence": _finite(
                    value.controllability_evidence, name="controllability evidence"
                ),
                "uncertainty": _finite(value.uncertainty, name="interoceptive uncertainty"),
                "vector": [_finite(item, name="interoceptive vector item") for item in value.vector],
            },
            "metacognition": {
                "state": metacognition.state.value,
                "margin": _finite(metacognition.margin, name="metacognitive margin"),
                "uncertainty": _finite(metacognition.uncertainty, name="metacognitive uncertainty"),
                "source_status": (
                    None
                    if metacognition.source_status is None
                    else metacognition.source_status.value
                ),
                "residual_energy": _finite(
                    metacognition.residual_energy, name="metacognitive residual energy"
                ),
            },
        }
        # A local JSON-safe walk catches accidental tensors/NaN if the core
        # readout contract changes, while not writing or retaining anything.
        self._assert_json_safe(context)
        return context

    @staticmethod
    def _assert_json_safe(value: object, *, path: str = "context") -> None:
        """Reject non-JSON-safe values and non-finite floats recursively."""

        if isinstance(value, bool) or value is None or isinstance(value, (str, int)):
            return
        if isinstance(value, float):
            if not math.isfinite(value):
                raise CassiConsciousCortexError(f"{path} contains a non-finite float")
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                CassiConsciousCortex._assert_json_safe(item, path=f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                if not isinstance(key, str):
                    raise CassiConsciousCortexError(f"{path} contains a non-string key")
                CassiConsciousCortex._assert_json_safe(item, path=f"{path}.{key}")
            return
        raise CassiConsciousCortexError(f"{path} contains a non-JSON value")


__all__ = [
    "CORTEX_PROFILE_ID",
    "CORTEX_SCHEMA",
    "DEFAULT_MAX_CANDIDATE_BYTES",
    "DEFAULT_MAX_CANDIDATE_COUNT",
    "MAX_CANDIDATE_COUNT",
    "MAX_IMAGINATION_STEPS",
    "CassiConsciousCortex",
    "CassiConsciousCortexError",
    "CortexCandidateResult",
    "CortexRanking",
]
