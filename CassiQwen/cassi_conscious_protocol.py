"""Immutable provenance protocol for conscious-field control.

The protocol records event identity, payload identity, and (when a caller
supplies an explicit tensor boundary) the exact tensor bytes that were applied.
The boundary digest is provenance for the transducer input; it is not a claim
that the event's source is truthful.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum


PROTOCOL_SCHEMA = "cassi.conscious.protocol.v2"
MAX_PAYLOAD_BYTES = 4096
TERMINAL_USER_SOURCE_ID = "terminal-user"

_SHA256_HEX_LENGTH = 64
_HEX_DIGITS = frozenset("0123456789abcdef")


class CassiConsciousProtocolError(ValueError):
    """Raised when an immutable conscious-field protocol value is invalid."""


class EventKind(str, Enum):
    """Kinds of events admitted by the conscious-field ledger."""

    PERCEPTION = "perception"
    ACTION_INTENT = "action_intent"
    COMMITMENT = "commitment"
    ACTION_OUTCOME = "action_outcome"
    RECALL = "recall"
    IMAGINATION = "imagination"
    TEACHER_PROPOSAL = "teacher_proposal"
    EXTERNAL_REPORT = "external_report"
    CONTRADICTION = "contradiction"
    DELIBERATION = "deliberation"
    FIELD_TEXT = "field_text"


class RealityStatus(str, Enum):
    """Reality/provenance status paired with an event kind."""
    OBSERVED_REALITY = "observed_reality"
    AGENT_INTENT = "agent_intent"
    HYPOTHESIS = "hypothesis"
    CONTRADICTION_FACT = "contradiction_fact"
    DERIVED_RECALL = "derived_recall"
    EXTERNAL_PROPOSAL = "external_proposal"
    REPORTED_EVIDENCE = "reported_evidence"
    DERIVED_DELIBERATION = "derived_deliberation"
    FIELD_EMISSION = "field_emission"


class ActorClass(str, Enum):
    """Actor classes permitted by the event legality table."""

    LOCAL_AGENT = "local_agent"
    EXTERNAL_AGENT = "external_agent"
    TEACHER = "teacher"
    ENVIRONMENT = "environment"
    UNKNOWN = "unknown"


class BranchStatus(str, Enum):
    """Lifecycle status for an imagination branch."""

    OPEN = "open"
    CONFIRMED = "confirmed"
    CONTRADICTED = "contradicted"


_LEGAL: dict[EventKind, tuple[RealityStatus, frozenset[ActorClass]]] = {
    EventKind.PERCEPTION: (
        RealityStatus.OBSERVED_REALITY,
        frozenset(
            {
                ActorClass.ENVIRONMENT,
                ActorClass.EXTERNAL_AGENT,
                ActorClass.UNKNOWN,
            }
        ),
    ),
    EventKind.ACTION_INTENT: (
        RealityStatus.AGENT_INTENT,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
    EventKind.COMMITMENT: (
        RealityStatus.AGENT_INTENT,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
    EventKind.ACTION_OUTCOME: (
        RealityStatus.OBSERVED_REALITY,
        frozenset({
            ActorClass.ENVIRONMENT,
            ActorClass.EXTERNAL_AGENT,
            ActorClass.LOCAL_AGENT,
            ActorClass.UNKNOWN,
        }),
    ),
    EventKind.RECALL: (
        RealityStatus.DERIVED_RECALL,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
    EventKind.DELIBERATION: (
        RealityStatus.DERIVED_DELIBERATION,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
    EventKind.FIELD_TEXT: (
        RealityStatus.FIELD_EMISSION,
        frozenset({ActorClass.LOCAL_AGENT, ActorClass.EXTERNAL_AGENT}),
    ),
    EventKind.IMAGINATION: (
        RealityStatus.HYPOTHESIS,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
    EventKind.TEACHER_PROPOSAL: (
        RealityStatus.EXTERNAL_PROPOSAL,
        frozenset({ActorClass.TEACHER, ActorClass.EXTERNAL_AGENT}),
    ),
    EventKind.EXTERNAL_REPORT: (
        RealityStatus.REPORTED_EVIDENCE,
        frozenset({ActorClass.EXTERNAL_AGENT, ActorClass.TEACHER}),
    ),
    EventKind.CONTRADICTION: (
        RealityStatus.CONTRADICTION_FACT,
        frozenset({ActorClass.LOCAL_AGENT}),
    ),
}


def _validate_digest(name: str, value: str, *, allow_empty: bool) -> None:
    """Validate a lower-case hexadecimal SHA-256 digest."""

    if not isinstance(value, str):
        raise CassiConsciousProtocolError(f"{name} must be a lowercase SHA-256 digest")
    if value == "":
        if allow_empty:
            return
        raise CassiConsciousProtocolError(f"{name} must be a lowercase SHA-256 digest")
    if len(value) != _SHA256_HEX_LENGTH or any(character not in _HEX_DIGITS for character in value):
        raise CassiConsciousProtocolError(f"{name} must be a lowercase SHA-256 digest")


def _validate_text(name: str, value: str, *, allow_empty: bool = False) -> None:
    """Validate bounded source and identifier strings."""

    if not isinstance(value, str) or (not allow_empty and value == "") or len(value) > 256:
        raise CassiConsciousProtocolError(f"{name} must be a bounded string")


def _canonical_event_body(
    *,
    sequence: int,
    parent_event_id: str,
    branch_id: str,
    kind: EventKind,
    reality_status: RealityStatus,
    actor: ActorClass,
    payload: bytes,
    source_id: str,
    boundary_wave_sha256: str,
) -> bytes:
    """Return the canonical JSON bytes used for the immutable event ID."""

    body = {
        "actor": actor.value,
        "boundary_wave_sha256": boundary_wave_sha256,
        "branch_id": branch_id,
        "kind": kind.value,
        "parent_event_id": parent_event_id,
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
        "reality_status": reality_status.value,
        "schema": PROTOCOL_SCHEMA,
        "sequence": sequence,
        "source_id": source_id,
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":")).encode("ascii")


@dataclass(frozen=True)
class CassiExperienceEvent:
    """An immutable, canonically hashed experience event."""

    event_id: str
    sequence: int
    parent_event_id: str
    branch_id: str
    kind: EventKind
    reality_status: RealityStatus
    actor: ActorClass
    payload: bytes
    source_id: str
    payload_sha256: str
    boundary_wave_sha256: str = ""

    def canonical_bytes(self) -> bytes:
        """Validate and return the canonical event-ID payload."""

        validate_event(self)
        return _canonical_event_body(
            sequence=self.sequence,
            parent_event_id=self.parent_event_id,
            branch_id=self.branch_id,
            kind=self.kind,
            reality_status=self.reality_status,
            actor=self.actor,
            payload=self.payload,
            source_id=self.source_id,
            boundary_wave_sha256=self.boundary_wave_sha256,
        )


@dataclass(frozen=True)
class CassiPredictionReceipt:
    """Hashes and scalar readout required to authenticate an open branch."""

    branch_id: str
    root_field_sha256: str
    root_event_id: str
    proposal_event_sha256: str
    proposal_wave_sha256: str
    imagination_steps: int
    predicted_symbol: int
    readout_sha256: str
    access_granted: bool

    def __post_init__(self) -> None:
        for name in (
            "branch_id",
            "root_field_sha256",
            "proposal_event_sha256",
            "proposal_wave_sha256",
            "readout_sha256",
        ):
            _validate_digest(name, getattr(self, name), allow_empty=False)
        _validate_digest("root_event_id", self.root_event_id, allow_empty=True)
        if (
            isinstance(self.imagination_steps, bool)
            or not isinstance(self.imagination_steps, int)
            or self.imagination_steps < 1
            or isinstance(self.predicted_symbol, bool)
            or not isinstance(self.predicted_symbol, int)
            or self.predicted_symbol < 0
            or not isinstance(self.access_granted, bool)
        ):
            raise CassiConsciousProtocolError("invalid prediction receipt")


@dataclass(frozen=True)
class CassiContradictionReceipt:
    """Hashes describing a proposal/observation comparison."""

    branch_id: str
    proposal_event_sha256: str
    actual_event_sha256: str
    proposal_wave_sha256: str
    predicted_wave_sha256: str
    actual_wave_sha256: str
    residual_sha256: str
    matched: bool

    def __post_init__(self) -> None:
        for name in (
            "branch_id",
            "proposal_event_sha256",
            "actual_event_sha256",
            "proposal_wave_sha256",
            "predicted_wave_sha256",
            "actual_wave_sha256",
            "residual_sha256",
        ):
            _validate_digest(name, getattr(self, name), allow_empty=False)
        if not isinstance(self.matched, bool):
            raise CassiConsciousProtocolError("matched must be boolean")


def create_event(
    *,
    sequence: int,
    kind: EventKind,
    reality_status: RealityStatus,
    actor: ActorClass,
    payload: bytes,
    source_id: str,
    parent_event_id: str = "",
    branch_id: str = "",
    boundary_wave_sha256: str = "",
) -> CassiExperienceEvent:
    """Create and validate a canonically hashed event.

    ``boundary_wave_sha256`` is intentionally optional for ordinary byte
    boundary events.  Core field methods require it whenever a caller supplies
    an explicit tensor wave.
    """

    if isinstance(sequence, bool) or not isinstance(sequence, int) or sequence < 0:
        raise CassiConsciousProtocolError("sequence must be a non-negative integer")
    if not isinstance(payload, bytes) or len(payload) > MAX_PAYLOAD_BYTES:
        raise CassiConsciousProtocolError("payload must be bounded bytes")
    if (
        not isinstance(kind, EventKind)
        or not isinstance(reality_status, RealityStatus)
        or not isinstance(actor, ActorClass)
    ):
        raise CassiConsciousProtocolError("protocol enums required")
    _validate_text("source_id", source_id)
    _validate_digest("parent_event_id", parent_event_id, allow_empty=True)
    _validate_digest("branch_id", branch_id, allow_empty=True)
    _validate_digest("boundary_wave_sha256", boundary_wave_sha256, allow_empty=True)
    expected_status, legal_actors = _LEGAL[kind]
    if reality_status is not expected_status or actor not in legal_actors:
        raise CassiConsciousProtocolError("illegal kind/reality/actor combination")

    event_id = hashlib.sha256(
        _canonical_event_body(
            sequence=sequence,
            parent_event_id=parent_event_id,
            branch_id=branch_id,
            kind=kind,
            reality_status=reality_status,
            actor=actor,
            payload=payload,
            source_id=source_id,
            boundary_wave_sha256=boundary_wave_sha256,
        )
    ).hexdigest()
    event = CassiExperienceEvent(
        event_id=event_id,
        sequence=sequence,
        parent_event_id=parent_event_id,
        branch_id=branch_id,
        kind=kind,
        reality_status=reality_status,
        actor=actor,
        payload=payload,
        source_id=source_id,
        payload_sha256=hashlib.sha256(payload).hexdigest(),
        boundary_wave_sha256=boundary_wave_sha256,
    )
    validate_event(event)
    return event


def validate_event(event: CassiExperienceEvent) -> None:
    """Validate event fields, legality, payload digest, and canonical ID."""

    if not isinstance(event, CassiExperienceEvent):
        raise CassiConsciousProtocolError("event type invalid")
    if (
        isinstance(event.sequence, bool)
        or not isinstance(event.sequence, int)
        or event.sequence < 0
        or not isinstance(event.payload, bytes)
        or len(event.payload) > MAX_PAYLOAD_BYTES
    ):
        raise CassiConsciousProtocolError("event fields invalid")
    if (
        not isinstance(event.kind, EventKind)
        or not isinstance(event.reality_status, RealityStatus)
        or not isinstance(event.actor, ActorClass)
    ):
        raise CassiConsciousProtocolError("event enums invalid")
    _validate_text("source_id", event.source_id)
    _validate_digest("event_id", event.event_id, allow_empty=False)
    _validate_digest("payload_sha256", event.payload_sha256, allow_empty=False)
    _validate_digest("parent_event_id", event.parent_event_id, allow_empty=True)
    _validate_digest("branch_id", event.branch_id, allow_empty=True)
    _validate_digest("boundary_wave_sha256", event.boundary_wave_sha256, allow_empty=True)
    expected_status, legal_actors = _LEGAL[event.kind]
    if event.reality_status is not expected_status or event.actor not in legal_actors:
        raise CassiConsciousProtocolError("illegal kind/reality/actor combination")
    expected_payload_hash = hashlib.sha256(event.payload).hexdigest()
    expected_event_hash = hashlib.sha256(
        _canonical_event_body(
            sequence=event.sequence,
            parent_event_id=event.parent_event_id,
            branch_id=event.branch_id,
            kind=event.kind,
            reality_status=event.reality_status,
            actor=event.actor,
            payload=event.payload,
            source_id=event.source_id,
            boundary_wave_sha256=event.boundary_wave_sha256,
        )
    ).hexdigest()
    if event.payload_sha256 != expected_payload_hash or event.event_id != expected_event_hash:
        raise CassiConsciousProtocolError("forged event hash")


__all__ = [
    "ActorClass",
    "BranchStatus",
    "CassiConsciousProtocolError",
    "CassiContradictionReceipt",
    "CassiExperienceEvent",
    "CassiPredictionReceipt",
    "MAX_PAYLOAD_BYTES",
    "PROTOCOL_SCHEMA",
    "RealityStatus",
    "TERMINAL_USER_SOURCE_ID",
    "create_event",
    "validate_event",
]
