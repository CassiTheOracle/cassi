"""Field-native federation contracts for independent Cassi instances.

The hive layer transports committed semantic discoveries. It never averages or
copies raw field tensors. Every object is immutable, content-addressed, and
bound to the field profile and predecessor lineage that produced it.
"""

from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass, replace
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from cassi_field_atlas import (
    FieldProgram,
    RelationChart,
    VariableSpec,
    canonical_json_bytes,
    sha256_value,
)
from cassi_field_owner import SourceInput


EXPERIENCE_SCHEMA = "cassifi.hive.experience.v1"
BUNDLE_SCHEMA = "cassifi.hive.bundle.v1"
ADOPTION_SCHEMA = "cassifi.hive.adoption.v1"
ATLAS_SCHEMA = "cassifi.field-atlas.v2"
REPRESENTATION_SCHEMA = "cassifi.shared-representation-registry.v1"
PORTABLE_TRANSFER_SCHEMA = "cassifi.hive.portable-transfer.v1"
PORTABLE_PROFILE_SHA256 = sha256_value(
    {"schema": PORTABLE_TRANSFER_SCHEMA, "surface": "field-program.v1"}
)

CANDIDATE_KINDS = frozenset(
    {
        "relation-chart",
        "temporal-prediction",
        "field-program",
        "language-construction",
        "action-schema",
        "representation",
        "procedure",
        "reasoning-strategy",
    }
)
REVIEW_TYPES = frozenset(
    {"independent-reproduction", "adversarial-review", "transfer-review"}
)
REVIEW_RESULTS = frozenset({"supports", "refutes", "inconclusive"})
ADOPTION_STATUSES = frozenset(
    {
        "accepted",
        "accepted-with-local-guard",
        "incompatible",
        "resource-exhausted",
        "refused",
        "replayed",
        "contradicted",
    }
)


class HiveProtocolError(ValueError):
    """Invalid hive object, lineage, compatibility, or admission result."""


def _freeze(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType({str(key): _freeze(item) for key, item in value.items()})
    if isinstance(value, (tuple, list)):
        return tuple(_freeze(item) for item in value)
    return value


def _plain(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_plain(item) for item in value]
    return value


def _json_mapping(value: Any, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise HiveProtocolError(f"{label} must be a mapping")
    try:
        parsed = json.loads(canonical_json_bytes(value).decode("utf-8"))
    except (TypeError, ValueError) as exc:
        raise HiveProtocolError(f"{label} must be canonical JSON") from exc
    if not isinstance(parsed, dict):
        raise HiveProtocolError(f"{label} must encode an object")
    return _freeze(parsed)


def _text(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or not value
        or len(value.encode("utf-8")) > 512
        or any(ord(character) < 32 for character in value)
    ):
        raise HiveProtocolError(f"{label} must be bounded nonempty text")
    return value


def _digest(value: Any, label: str) -> str:
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
    ):
        raise HiveProtocolError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _nonnegative_int(value: Any, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise HiveProtocolError(f"{label} must be a nonnegative integer")
    return value


def _finite_probability(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise HiveProtocolError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or not 0.0 <= result <= 1.0:
        raise HiveProtocolError(f"{label} must be finite and in [0, 1]")
    return result


def _digest_content(schema: str, content: Mapping[str, Any]) -> str:
    return sha256_value({"schema": schema, "content": _plain(content)})


def _tuple_text(values: Sequence[Any], label: str) -> tuple[str, ...]:
    if isinstance(values, (str, bytes)):
        raise HiveProtocolError(f"{label} must be a sequence")
    result = tuple(_text(value, label) for value in values)
    if len(set(result)) != len(result):
        raise HiveProtocolError(f"{label} must not contain duplicates")
    return result


def _tuple_mapping(values: Sequence[Any], label: str) -> tuple[Mapping[str, Any], ...]:
    if isinstance(values, (str, bytes)):
        raise HiveProtocolError(f"{label} must be a sequence")
    return tuple(_json_mapping(value, label) for value in values)


@dataclass(frozen=True, slots=True)
class ExperienceOrigin:
    instance_id: str
    role: str
    field_profile_sha256: str
    atlas_schema: str
    predecessor_manifest_sha256: str
    predecessor_state_sha256: str
    successor_manifest_sha256: str
    successor_state_sha256: str
    local_generation: int
    common_generation: int

    def __post_init__(self) -> None:
        for name in ("instance_id", "role", "atlas_schema"):
            _text(getattr(self, name), name)
        for name in (
            "field_profile_sha256",
            "predecessor_manifest_sha256",
            "predecessor_state_sha256",
            "successor_manifest_sha256",
            "successor_state_sha256",
        ):
            _digest(getattr(self, name), name)
        for name in ("local_generation", "common_generation"):
            _nonnegative_int(getattr(self, name), name)
        if self.atlas_schema != ATLAS_SCHEMA:
            raise HiveProtocolError("experience atlas schema is unsupported")
        if self.predecessor_state_sha256 == self.successor_state_sha256:
            raise HiveProtocolError("experience must name a state transition")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "atlas_schema": self.atlas_schema,
            "common_generation": self.common_generation,
            "field_profile_sha256": self.field_profile_sha256,
            "instance_id": self.instance_id,
            "local_generation": self.local_generation,
            "predecessor_manifest_sha256": self.predecessor_manifest_sha256,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "role": self.role,
            "successor_manifest_sha256": self.successor_manifest_sha256,
            "successor_state_sha256": self.successor_state_sha256,
        }


@dataclass(frozen=True, slots=True)
class ExperienceEpisode:
    task_id: str
    context: Mapping[str, Any]
    source_revision_ids: tuple[str, ...]
    observation_event_ids: tuple[str, ...]
    action: Mapping[str, Any]
    prediction: Mapping[str, Any]
    outcome: Mapping[str, Any]
    work_units: int
    uncertainty: float

    def __post_init__(self) -> None:
        _text(self.task_id, "task_id")
        object.__setattr__(self, "context", _json_mapping(self.context, "episode context"))
        object.__setattr__(self, "action", _json_mapping(self.action, "episode action"))
        object.__setattr__(self, "prediction", _json_mapping(self.prediction, "episode prediction"))
        object.__setattr__(self, "outcome", _json_mapping(self.outcome, "episode outcome"))
        object.__setattr__(
            self,
            "source_revision_ids",
            _tuple_text(self.source_revision_ids, "source revision id"),
        )
        object.__setattr__(
            self,
            "observation_event_ids",
            _tuple_text(self.observation_event_ids, "observation event id"),
        )
        _nonnegative_int(self.work_units, "work_units")
        object.__setattr__(
            self, "uncertainty", _finite_probability(self.uncertainty, "uncertainty")
        )

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "action": _plain(self.action),
            "context": _plain(self.context),
            "observation_event_ids": list(self.observation_event_ids),
            "outcome": _plain(self.outcome),
            "prediction": _plain(self.prediction),
            "source_revision_ids": list(self.source_revision_ids),
            "task_id": self.task_id,
            "uncertainty": self.uncertainty,
            "work_units": self.work_units,
        }


@dataclass(frozen=True, slots=True)
class ExperienceCandidate:
    kind: str
    object: Mapping[str, Any]
    operation_plan: tuple[Mapping[str, Any], ...]
    guards: tuple[Mapping[str, Any], ...]
    dependencies: tuple[str, ...]

    def __post_init__(self) -> None:
        if self.kind not in CANDIDATE_KINDS:
            raise HiveProtocolError("candidate kind is unsupported")
        object.__setattr__(self, "object", _json_mapping(self.object, "candidate object"))
        object.__setattr__(
            self,
            "operation_plan",
            _tuple_mapping(self.operation_plan, "candidate operation"),
        )
        object.__setattr__(self, "guards", _tuple_mapping(self.guards, "candidate guard"))
        object.__setattr__(
            self,
            "dependencies",
            _tuple_text(self.dependencies, "candidate dependency"),
        )
        if not self.operation_plan:
            raise HiveProtocolError("candidate operation plan cannot be empty")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "dependencies": list(self.dependencies),
            "guards": [_plain(item) for item in self.guards],
            "kind": self.kind,
            "object": _plain(self.object),
            "operation_plan": [_plain(item) for item in self.operation_plan],
        }


@dataclass(frozen=True, slots=True)
class ExperienceEvidence:
    support_event_ids: tuple[str, ...]
    assessment_ids: tuple[str, ...]
    held_out_results: tuple[Mapping[str, Any], ...]
    counterexamples: tuple[Mapping[str, Any], ...]
    derivation_roots: tuple[str, ...]

    def __post_init__(self) -> None:
        for name, value in (
            ("support_event_ids", self.support_event_ids),
            ("assessment_ids", self.assessment_ids),
            ("derivation_roots", self.derivation_roots),
        ):
            object.__setattr__(self, name, _tuple_text(value, name[:-4] if name.endswith("_ids") else name))
        object.__setattr__(
            self,
            "held_out_results",
            _tuple_mapping(self.held_out_results, "held-out result"),
        )
        object.__setattr__(
            self,
            "counterexamples",
            _tuple_mapping(self.counterexamples, "counterexample"),
        )
        if not self.support_event_ids and not self.assessment_ids:
            raise HiveProtocolError("experience evidence needs support or assessment ids")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "assessment_ids": list(self.assessment_ids),
            "counterexamples": [_plain(item) for item in self.counterexamples],
            "derivation_roots": list(self.derivation_roots),
            "held_out_results": [_plain(item) for item in self.held_out_results],
            "support_event_ids": list(self.support_event_ids),
        }


@dataclass(frozen=True, slots=True)
class TransferSpec:
    required_field_profile_sha256: str
    required_atlas_schema: str
    replay_mode: str
    maximum_admission_work: int
    visibility: str

    def __post_init__(self) -> None:
        _digest(self.required_field_profile_sha256, "required field profile")
        _text(self.required_atlas_schema, "required atlas schema")
        if self.required_atlas_schema != ATLAS_SCHEMA:
            raise HiveProtocolError("transfer atlas schema is unsupported")
        if self.replay_mode != "semantic":
            raise HiveProtocolError("only semantic replay is supported")
        _nonnegative_int(self.maximum_admission_work, "maximum admission work")
        if self.maximum_admission_work == 0:
            raise HiveProtocolError("maximum admission work must be positive")
        if self.visibility not in {"public", "provenance-only"}:
            raise HiveProtocolError("transfer visibility is unsupported")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "maximum_admission_work": self.maximum_admission_work,
            "replay_mode": self.replay_mode,
            "required_atlas_schema": self.required_atlas_schema,
            "required_field_profile_sha256": self.required_field_profile_sha256,
            "visibility": self.visibility,
        }


@dataclass(frozen=True, slots=True)
class ExperienceCapsule:
    hive_id: str
    origin: ExperienceOrigin
    episode: ExperienceEpisode
    candidate: ExperienceCandidate
    evidence: ExperienceEvidence
    transfer: TransferSpec

    def __post_init__(self) -> None:
        _text(self.hive_id, "hive_id")
        if self.transfer.required_field_profile_sha256 != self.origin.field_profile_sha256:
            raise HiveProtocolError("transfer profile differs from origin profile")

    @property
    def content(self) -> Mapping[str, Any]:
        return {
            "candidate": self.candidate.as_dict(),
            "episode": self.episode.as_dict(),
            "evidence": self.evidence.as_dict(),
            "hive_id": self.hive_id,
            "origin": self.origin.as_dict(),
            "transfer": self.transfer.as_dict(),
        }

    @property
    def content_sha256(self) -> str:
        return _digest_content(EXPERIENCE_SCHEMA, self.content)

    @property
    def object_id(self) -> str:
        return self.content_sha256

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "content": _plain(self.content),
            "content_sha256": self.content_sha256,
            "object_id": self.object_id,
            "schema": EXPERIENCE_SCHEMA,
        }


@dataclass(frozen=True, slots=True)
class Review:
    reviewer_instance_id: str
    review_type: str
    result: str
    evidence_ids: tuple[str, ...]

    def __post_init__(self) -> None:
        _text(self.reviewer_instance_id, "reviewer instance id")
        if self.review_type not in REVIEW_TYPES:
            raise HiveProtocolError("review type is unsupported")
        if self.result not in REVIEW_RESULTS:
            raise HiveProtocolError("review result is unsupported")
        object.__setattr__(self, "evidence_ids", _tuple_text(self.evidence_ids, "review evidence id"))
        if not self.evidence_ids:
            raise HiveProtocolError("review needs evidence ids")

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "evidence_ids": list(self.evidence_ids),
            "result": self.result,
            "review_type": self.review_type,
            "reviewer_instance_id": self.reviewer_instance_id,
        }


@dataclass(frozen=True, slots=True)
class KnowledgeBundle:
    hive_id: str
    leader_instance_id: str
    authority_grant_sha256: str
    predecessor_common_generation: int
    resulting_common_generation: int
    source_experience_ids: tuple[str, ...]
    learned_objects: tuple[Mapping[str, Any], ...]
    operation_plan: tuple[Mapping[str, Any], ...]
    guards: tuple[Mapping[str, Any], ...]
    dependencies: tuple[str, ...]
    compatibility: Mapping[str, Any]
    reviews: tuple[Review, ...]
    known_exceptions: tuple[Mapping[str, Any], ...]
    revocation_conditions: tuple[Mapping[str, Any], ...]
    status: str = "promoted"

    def __post_init__(self) -> None:
        _text(self.hive_id, "hive_id")
        _text(self.leader_instance_id, "leader instance id")
        _digest(self.authority_grant_sha256, "authority grant")
        _nonnegative_int(self.predecessor_common_generation, "predecessor common generation")
        _nonnegative_int(self.resulting_common_generation, "resulting common generation")
        if self.resulting_common_generation != self.predecessor_common_generation + 1:
            raise HiveProtocolError("bundle must advance common generation by one")
        object.__setattr__(
            self,
            "source_experience_ids",
            _tuple_text(self.source_experience_ids, "source experience id"),
        )
        if not self.source_experience_ids:
            raise HiveProtocolError("bundle needs source experiences")
        object.__setattr__(self, "learned_objects", _tuple_mapping(self.learned_objects, "learned object"))
        object.__setattr__(self, "operation_plan", _tuple_mapping(self.operation_plan, "bundle operation"))
        object.__setattr__(self, "guards", _tuple_mapping(self.guards, "bundle guard"))
        object.__setattr__(self, "dependencies", _tuple_text(self.dependencies, "bundle dependency"))
        object.__setattr__(self, "compatibility", _json_mapping(self.compatibility, "bundle compatibility"))
        object.__setattr__(self, "reviews", tuple(self.reviews))
        object.__setattr__(self, "known_exceptions", _tuple_mapping(self.known_exceptions, "known exception"))
        object.__setattr__(self, "revocation_conditions", _tuple_mapping(self.revocation_conditions, "revocation condition"))
        if self.status != "promoted":
            raise HiveProtocolError("only promoted bundles can be dispatched")
        if not self.learned_objects or not self.operation_plan:
            raise HiveProtocolError("bundle needs learned objects and operations")
        if not self.reviews:
            raise HiveProtocolError("bundle needs independent reviews")
        if not any(review.result == "supports" for review in self.reviews):
            raise HiveProtocolError("bundle needs a supporting review")

    @property
    def content(self) -> Mapping[str, Any]:
        return {
            "authority_grant_sha256": self.authority_grant_sha256,
            "compatibility": _plain(self.compatibility),
            "dependencies": list(self.dependencies),
            "guards": [_plain(item) for item in self.guards],
            "hive_id": self.hive_id,
            "known_exceptions": [_plain(item) for item in self.known_exceptions],
            "leader_instance_id": self.leader_instance_id,
            "learned_objects": [_plain(item) for item in self.learned_objects],
            "operation_plan": [_plain(item) for item in self.operation_plan],
            "predecessor_common_generation": self.predecessor_common_generation,
            "resulting_common_generation": self.resulting_common_generation,
            "revocation_conditions": [_plain(item) for item in self.revocation_conditions],
            "reviews": [review.as_dict() for review in self.reviews],
            "source_experience_ids": list(self.source_experience_ids),
            "status": self.status,
        }

    @property
    def content_sha256(self) -> str:
        return _digest_content(BUNDLE_SCHEMA, self.content)

    @property
    def object_id(self) -> str:
        return self.content_sha256

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "content": _plain(self.content),
            "content_sha256": self.content_sha256,
            "object_id": self.object_id,
            "schema": BUNDLE_SCHEMA,
        }


@dataclass(frozen=True, slots=True)
class AdoptionReceipt:
    hive_id: str
    bundle_id: str
    recipient_instance_id: str
    predecessor_manifest_sha256: str
    predecessor_state_sha256: str
    successor_manifest_sha256: str
    successor_state_sha256: str
    expected_common_generation: int
    resulting_common_generation: int
    status: str
    applied_object_ids: tuple[str, ...]
    refused_object_ids: tuple[str, ...]
    incompatible_object_ids: tuple[str, ...]
    contradicted_object_ids: tuple[str, ...]
    baseline_observation_ids: tuple[str, ...]
    post_adoption_observation_ids: tuple[str, ...]
    behavioral_delta: Mapping[str, Any]
    field_effect_confirmed: bool

    def __post_init__(self) -> None:
        _text(self.hive_id, "hive_id")
        _digest(self.bundle_id, "bundle id")
        _text(self.recipient_instance_id, "recipient instance id")
        for name in (
            "predecessor_manifest_sha256",
            "predecessor_state_sha256",
            "successor_manifest_sha256",
            "successor_state_sha256",
        ):
            _digest(getattr(self, name), name)
        _nonnegative_int(self.expected_common_generation, "expected common generation")
        _nonnegative_int(self.resulting_common_generation, "resulting common generation")
        if self.status not in ADOPTION_STATUSES:
            raise HiveProtocolError("adoption status is unsupported")
        for name in (
            "applied_object_ids",
            "refused_object_ids",
            "incompatible_object_ids",
            "contradicted_object_ids",
            "baseline_observation_ids",
            "post_adoption_observation_ids",
        ):
            object.__setattr__(self, name, _tuple_text(getattr(self, name), name[:-4] if name.endswith("_ids") else name))
        object.__setattr__(self, "behavioral_delta", _json_mapping(self.behavioral_delta, "behavioral delta"))
        if not isinstance(self.field_effect_confirmed, bool):
            raise HiveProtocolError("field effect confirmation must be Boolean")
        if self.status in {"accepted", "accepted-with-local-guard"}:
            if self.successor_state_sha256 == self.predecessor_state_sha256:
                raise HiveProtocolError("accepted adoption must publish a successor state")
            if not self.applied_object_ids:
                raise HiveProtocolError("accepted adoption must name applied objects")
        else:
            if self.successor_state_sha256 != self.predecessor_state_sha256:
                raise HiveProtocolError("rejected adoption cannot publish a successor")

    @property
    def content(self) -> Mapping[str, Any]:
        return {
            "applied_object_ids": list(self.applied_object_ids),
            "baseline_observation_ids": list(self.baseline_observation_ids),
            "behavioral_delta": _plain(self.behavioral_delta),
            "bundle_id": self.bundle_id,
            "contradicted_object_ids": list(self.contradicted_object_ids),
            "expected_common_generation": self.expected_common_generation,
            "field_effect_confirmed": self.field_effect_confirmed,
            "hive_id": self.hive_id,
            "incompatible_object_ids": list(self.incompatible_object_ids),
            "post_adoption_observation_ids": list(self.post_adoption_observation_ids),
            "predecessor_manifest_sha256": self.predecessor_manifest_sha256,
            "predecessor_state_sha256": self.predecessor_state_sha256,
            "recipient_instance_id": self.recipient_instance_id,
            "refused_object_ids": list(self.refused_object_ids),
            "resulting_common_generation": self.resulting_common_generation,
            "status": self.status,
            "successor_manifest_sha256": self.successor_manifest_sha256,
            "successor_state_sha256": self.successor_state_sha256,
        }

    @property
    def content_sha256(self) -> str:
        return _digest_content(ADOPTION_SCHEMA, self.content)

    @property
    def object_id(self) -> str:
        return self.content_sha256

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "content": _plain(self.content),
            "content_sha256": self.content_sha256,
            "object_id": self.object_id,
            "schema": ADOPTION_SCHEMA,
        }


def _portable_bundle_for_profile(
    bundle: KnowledgeBundle,
    field_profile_sha256: str,
) -> bool:
    """Return whether a bundle uses the explicit portable field-program seam."""

    compatibility = bundle.compatibility
    if compatibility.get("portable_transfer_schema") != PORTABLE_TRANSFER_SCHEMA:
        return False
    if compatibility.get("field_profile_sha256") != PORTABLE_PROFILE_SHA256:
        return False
    if compatibility.get("atlas_schema") != ATLAS_SCHEMA:
        return False
    source_profiles = compatibility.get("source_field_profile_sha256s")
    if (
        isinstance(source_profiles, (str, bytes))
        or not isinstance(source_profiles, Sequence)
        or not source_profiles
        or any(
            not isinstance(profile, str)
            or len(profile) != 64
            or any(character not in "0123456789abcdef" for character in profile)
            for profile in source_profiles
        )
    ):
        return False
    if not isinstance(field_profile_sha256, str) or len(field_profile_sha256) != 64:
        return False
    if len(bundle.operation_plan) != 1:
        return False
    if bundle.operation_plan[0].get("operation") not in {
        "configure-program",
        "promote-program",
    }:
        return False
    learned = bundle.learned_objects
    if len(learned) != 1 or learned[0].get("kind") != "field-program":
        return False
    return True


def build_knowledge_bundle(
    capsules: Sequence[ExperienceCapsule],
    *,
    leader_instance_id: str,
    authority_grant_sha256: str,
    predecessor_common_generation: int,
    reviews: Sequence[Review],
    minimum_support_reviews: int = 1,
) -> KnowledgeBundle:
    """Consolidate compatible capsules into one promoted semantic bundle."""

    if isinstance(capsules, (str, bytes)) or not capsules:
        raise HiveProtocolError("bundle needs at least one experience capsule")
    if isinstance(reviews, (str, bytes)):
        raise HiveProtocolError("reviews must be a sequence")
    capsule_rows = tuple(capsules)
    if any(not isinstance(capsule, ExperienceCapsule) for capsule in capsule_rows):
        raise HiveProtocolError("bundle capsules must be ExperienceCapsule values")
    _text(leader_instance_id, "leader instance id")
    _digest(authority_grant_sha256, "authority grant")
    first = capsule_rows[0]
    portable = (
        first.candidate.kind == "field-program"
        and first.candidate.object.get("portable_transfer") is True
    )
    for capsule in capsule_rows[1:]:
        if capsule.hive_id != first.hive_id:
            raise HiveProtocolError("capsules belong to different hives")
        if capsule.origin.field_profile_sha256 != first.origin.field_profile_sha256:
            if not portable:
                raise HiveProtocolError("capsules use different field profiles")
        if capsule.candidate.kind != first.candidate.kind or capsule.candidate.object != first.candidate.object:
            raise HiveProtocolError("capsules carry incompatible candidates")
    if portable:
        if first.candidate.kind != "field-program" or len(first.candidate.operation_plan) != 1:
            raise HiveProtocolError("portable transfer requires one field-program operation")
        if first.candidate.operation_plan[0].get("operation") not in {
            "configure-program",
            "promote-program",
        }:
            raise HiveProtocolError("portable transfer operation is unsupported")
    if any(capsule.origin.common_generation > predecessor_common_generation for capsule in capsule_rows):
        raise HiveProtocolError("capsule common generation is ahead of bundle predecessor")

    review_rows = tuple(reviews)
    if any(not isinstance(review, Review) for review in review_rows):
        raise HiveProtocolError("bundle reviews must be Review values")
    origin_ids = {capsule.origin.instance_id for capsule in capsule_rows}
    reviewer_ids = {review.reviewer_instance_id for review in review_rows}
    if origin_ids & reviewer_ids:
        raise HiveProtocolError("originating instances cannot independently review their own capsule")
    support_count = sum(review.result == "supports" for review in review_rows)
    if support_count < minimum_support_reviews:
        raise HiveProtocolError("bundle lacks the required independent support reviews")
    if len(reviewer_ids) != len(review_rows):
        raise HiveProtocolError("bundle reviews must come from distinct instances")

    candidate = first.candidate
    source_profiles = sorted(
        {capsule.origin.field_profile_sha256 for capsule in capsule_rows}
    )
    compatibility = {
        "atlas_schema": first.origin.atlas_schema,
        "field_profile_sha256": (
            PORTABLE_PROFILE_SHA256 if portable else first.origin.field_profile_sha256
        ),
        "representation_schema": REPRESENTATION_SCHEMA,
        "required_object_ids": list(candidate.dependencies),
        "maximum_work": first.transfer.maximum_admission_work,
    }
    if portable:
        compatibility.update(
            {
                "portable_transfer_schema": PORTABLE_TRANSFER_SCHEMA,
                "source_field_profile_sha256s": source_profiles,
            }
        )
    return KnowledgeBundle(
        hive_id=first.hive_id,
        leader_instance_id=leader_instance_id,
        authority_grant_sha256=authority_grant_sha256,
        predecessor_common_generation=predecessor_common_generation,
        resulting_common_generation=predecessor_common_generation + 1,
        source_experience_ids=tuple(capsule.object_id for capsule in capsule_rows),
        learned_objects=(
            {"kind": candidate.kind, "object": _plain(candidate.object)},
        ),
        operation_plan=candidate.operation_plan,
        guards=candidate.guards,
        dependencies=candidate.dependencies,
        compatibility=compatibility,
        reviews=review_rows,
        known_exceptions=tuple(
            item for capsule in capsule_rows for item in capsule.evidence.counterexamples
        ),
        revocation_conditions=(),
    )

def capsule_from_owner_transition(
    owner: Any,
    transition: Mapping[str, Any],
    *,
    hive_id: str,
    instance_id: str,
    role: str,
    field_profile_sha256: str,
    common_generation: int,
    task_id: str,
    context: Mapping[str, Any],
    action: Mapping[str, Any],
    prediction: Mapping[str, Any],
    outcome: Mapping[str, Any],
    candidate: ExperienceCandidate,
    evidence: ExperienceEvidence,
    transfer_visibility: str = "public",
    maximum_admission_work: int = 4096,
    verify_checkpoints: bool = True,
    predecessor_state_sha256: str | None = None,
) -> ExperienceCapsule:
    """Extract one capsule from a committed FieldIntelligenceOwner result.

    The owner remains the source of truth for predecessor and successor state
    identity. The adapter accepts a result mapping or a mapping containing its
    ``receipt`` field, and verifies both checkpoint states through the owner's
    retained checkpoint store before constructing the capsule.
    """

    if not isinstance(transition, Mapping):
        raise HiveProtocolError("owner transition must be a mapping")
    raw_receipt = transition.get("receipt", transition)
    if not isinstance(raw_receipt, Mapping):
        raise HiveProtocolError("owner transition receipt must be a mapping")
    required = {
        "operation_id",
        "manifest_sha256",
        "state_sha256",
        "predecessor_manifest_sha256",
        "generation",
    }
    if not required.issubset(raw_receipt):
        raise HiveProtocolError("owner receipt lacks committed lineage fields")
    if not hasattr(owner, "checkpoints") or not hasattr(owner, "state"):
        raise HiveProtocolError("owner does not expose checkpoint lineage")

    predecessor_manifest = _digest(
        raw_receipt["predecessor_manifest_sha256"],
        "owner predecessor manifest",
    )
    successor_manifest = _digest(
        raw_receipt["manifest_sha256"],
        "owner successor manifest",
    )
    if verify_checkpoints:
        predecessor_state = owner.checkpoints.load_version(predecessor_manifest)
        successor_state = owner.checkpoints.load_version(successor_manifest)
        predecessor_state_sha256 = predecessor_state.state_sha256
        successor_state_sha256 = successor_state.state_sha256
    else:
        if predecessor_state_sha256 is None:
            raise HiveProtocolError(
                "fast capsule verification needs predecessor state"
            )
        predecessor_state_sha256 = _digest(
            predecessor_state_sha256,
            "owner predecessor state",
        )
        successor_state_sha256 = _digest(
            raw_receipt["state_sha256"],
            "owner state",
        )
    if successor_state_sha256 != _digest(raw_receipt["state_sha256"], "owner state"):
        raise HiveProtocolError("owner receipt state does not match retained checkpoint")
    if successor_state_sha256 == predecessor_state_sha256:
        raise HiveProtocolError("owner receipt did not commit a state transition")
    if owner.state.state_sha256 != successor_state_sha256:
        raise HiveProtocolError("owner receipt is not the current owner head")

    origin = ExperienceOrigin(
        instance_id=instance_id,
        role=role,
        field_profile_sha256=field_profile_sha256,
        atlas_schema=ATLAS_SCHEMA,
        predecessor_manifest_sha256=predecessor_manifest,
        predecessor_state_sha256=predecessor_state_sha256,
        successor_manifest_sha256=successor_manifest,
        successor_state_sha256=successor_state_sha256,
        local_generation=_nonnegative_int(raw_receipt["generation"], "owner generation"),
        common_generation=common_generation,
    )
    source_revision_ids = tuple(
        str(transition["source"]["revision_id"])
        for _ in (0,)
        if isinstance(transition.get("source"), Mapping)
        and "revision_id" in transition["source"]
    )
    observation_event_ids = tuple(
        str(transition["event"]["event_id"])
        for _ in (0,)
        if isinstance(transition.get("event"), Mapping)
        and "event_id" in transition["event"]
    )
    episode = ExperienceEpisode(
        task_id=task_id,
        context=context,
        source_revision_ids=source_revision_ids,
        observation_event_ids=observation_event_ids,
        action=action,
        prediction=prediction,
        outcome=outcome,
        work_units=0,
        uncertainty=0.0,
    )
    return ExperienceCapsule(
        hive_id=hive_id,
        origin=origin,
        episode=episode,
        candidate=candidate,
        evidence=evidence,
        transfer=TransferSpec(
            required_field_profile_sha256=field_profile_sha256,
            required_atlas_schema=ATLAS_SCHEMA,
            replay_mode="semantic",
            maximum_admission_work=maximum_admission_work,
            visibility=transfer_visibility,
        ),
    )


def _preflight_multi_program_entries(entries: Sequence[Any]) -> None:
    if (
        isinstance(entries, (str, bytes))
        or not isinstance(entries, Sequence)
        or not entries
    ):
        raise HiveProtocolError("multi-program operation entries are invalid")
    program_ids: set[str] = set()

    def valid_witness(
        row: Any,
        *,
        assessment: bool,
        require_resolution: bool = False,
    ) -> bool:
        if not isinstance(row, Mapping):
            return False
        try:
            source_payload = dict(row["source"])
            if isinstance(source_payload.get("labels"), tuple):
                source_payload["labels"] = list(source_payload["labels"])
            if isinstance(source_payload.get("span"), tuple):
                source_payload["span"] = list(source_payload["span"])
            SourceInput.from_dict(source_payload)
        except Exception:
            return False
        values = row.get("values")
        context = row.get("context")
        if not isinstance(values, Mapping) or not isinstance(context, Mapping):
            return False
        for key, value in values.items():
            if (
                not isinstance(key, str)
                or isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
            ):
                return False
        roots = row.get("derivation_roots", ())
        if isinstance(roots, (str, bytes)) or not isinstance(roots, Sequence):
            return False
        resolution_floor = row.get("resolution_floor")
        resolution_status = row.get("resolution_status")
        if resolution_floor is not None and (
            isinstance(resolution_floor, bool)
            or not isinstance(resolution_floor, (int, float))
            or not math.isfinite(float(resolution_floor))
            or float(resolution_floor) < 0
        ):
            return False
        if resolution_status is not None and resolution_status not in {
            "resolved",
            "unresolved",
        }:
            return False
        if resolution_status == "unresolved" and resolution_floor is None:
            return False
        if require_resolution and (
            resolution_status is None or resolution_floor is None
        ):
            return False
        if assessment:
            loss_scale = row.get("loss_scale")
            if (
                not isinstance(row.get("bindings"), Mapping)
                or not isinstance(row.get("outcome"), Mapping)
                or isinstance(loss_scale, bool)
                or not isinstance(loss_scale, (int, float))
                or not math.isfinite(float(loss_scale))
                or float(loss_scale) < 0
            ):
                return False
        return True

    def valid_setup(entry: Mapping[str, Any]) -> bool:
        raw_variables = entry.get("variable_specs")
        raw_charts = entry.get("chart_specs")
        if (
            isinstance(raw_variables, (str, bytes))
            or not isinstance(raw_variables, Sequence)
            or isinstance(raw_charts, (str, bytes))
            or not isinstance(raw_charts, Sequence)
        ):
            return False
        try:
            for row in raw_variables:
                if not isinstance(row, Mapping):
                    return False
                VariableSpec.from_dict(dict(row))
            for row in raw_charts:
                if not isinstance(row, Mapping):
                    return False
                RelationChart.empty(
                    chart_id=row["chart_id"],
                    scope=tuple(row["scope"]),
                    ridge=row["ridge"],
                    observation_norm_bound=row["observation_norm_bound"],
                    prior_mass=row["prior_mass"],
                )
        except Exception:
            return False
        return True

    for entry in entries:
        if not isinstance(entry, Mapping):
            raise HiveProtocolError("multi-program entry is not an object")
        operation_kind = entry.get("operation")
        if operation_kind not in {"configure-program", "promote-program"}:
            raise HiveProtocolError("multi-program entry operation is unsupported")
        payload = entry.get("program")
        if not isinstance(payload, Mapping):
            raise HiveProtocolError("multi-program entry lacks a program")
        try:
            program = FieldProgram.from_dict(payload)
        except Exception as exc:
            raise HiveProtocolError("multi-program entry program is invalid") from exc
        if program.program_id in program_ids:
            raise HiveProtocolError("multi-program entries reuse a program identity")
        program_ids.add(program.program_id)
        if operation_kind == "configure-program":
            held_out = entry.get("held_out_witness")
            if held_out is not None and not valid_witness(held_out, assessment=True):
                raise HiveProtocolError("multi-program held-out witness is invalid")
            continue
        if program.status != "candidate":
            raise HiveProtocolError("multi-program promotion needs a candidate")
        raw_minimum = entry.get("minimum_assessments")
        raw_maximum = entry.get("maximum_average_loss")
        raw_penalty = entry.get("bit_penalty")
        if (
            isinstance(raw_minimum, bool)
            or not isinstance(raw_minimum, int)
            or raw_minimum < 1
            or isinstance(raw_maximum, bool)
            or not isinstance(raw_maximum, (int, float))
            or not math.isfinite(float(raw_maximum))
            or not 0 <= float(raw_maximum) <= 1
            or isinstance(raw_penalty, bool)
            or not isinstance(raw_penalty, (int, float))
            or not math.isfinite(float(raw_penalty))
            or float(raw_penalty) < 0
        ):
            raise HiveProtocolError("multi-program promotion thresholds are invalid")
        replay_mode = (
            "support_witnesses" in entry or "assessment_witnesses" in entry
        )
        if replay_mode:
            support = entry.get("support_witnesses")
            assessments = entry.get("assessment_witnesses")
            if (
                isinstance(support, (str, bytes))
                or not isinstance(support, Sequence)
                or isinstance(assessments, (str, bytes))
                or not isinstance(assessments, Sequence)
                or len(assessments) < raw_minimum
                or not valid_setup(entry)
                or any(not valid_witness(row, assessment=False) for row in support)
                or any(
                    not valid_witness(
                        row,
                        assessment=True,
                        require_resolution=True,
                    )
                    for row in assessments
                )
            ):
                raise HiveProtocolError("multi-program replay witnesses are invalid")
            if program.assessments:
                raise HiveProtocolError("multi-program candidate must be unassessed")
        held_out = entry.get("held_out_witness")
        if held_out is not None and not valid_witness(held_out, assessment=True):
            raise HiveProtocolError("multi-program held-out witness is invalid")


def _verify_resolution_provenance(
    witness: Mapping[str, Any],
    assessment: Mapping[str, Any],
) -> None:
    expected_status = witness.get("resolution_status")
    if expected_status is not None and assessment.get("resolution_status") != expected_status:
        raise HiveProtocolError("resolution status changed during replay")
    expected_floor = witness.get("resolution_floor")
    if expected_floor is not None and not math.isclose(
        float(assessment.get("resolution_floor", -1.0)),
        float(expected_floor),
        rel_tol=1e-12,
        abs_tol=1e-24,
    ):
        raise HiveProtocolError("resolution floor changed during replay")


def _require_resolved_assessment(
    assessment: Mapping[str, Any],
    label: str,
) -> None:
    if assessment.get("resolution_status") != "resolved":
        raise HiveProtocolError(f"cannot transfer an unresolved {label}")


def _chart_replay_semantically_matches(existing: Any, requested: Any) -> bool:
    return (
        existing.chart_id == requested.chart_id
        and existing.scope == requested.scope
        and existing.ridge == requested.ridge
        and existing.observation_norm_bound == requested.observation_norm_bound
        and existing.prior_mass == requested.prior_mass
        and existing.factor_weight == requested.factor_weight
        and existing.learning_mode == requested.learning_mode
        and existing.recency_half_life == requested.recency_half_life
        and existing.guards == requested.guards
        and existing.mode_group == requested.mode_group
        and existing.mode == requested.mode
        and existing.representation_id == requested.representation_id
        and existing.dependencies == requested.dependencies
        and existing.status == requested.status
    )


def _rollback_multi_program_transaction(transaction: Any) -> None:
    try:
        transaction.rollback()
    except BaseException as exc:
        raise HiveProtocolError(
            "multi-program rollback failed; owner requires recovery"
        ) from exc


def _apply_multi_program_bundle(
    owner: Any,
    bundle: KnowledgeBundle,
    *,
    recipient_instance_id: str,
    field_profile_sha256: str,
    current_common_generation: int,
    available_object_ids: Sequence[str],
    revoked_bundle_ids: Sequence[str],
    baseline_observation_ids: Sequence[str],
    post_adoption_observation_ids: Sequence[str],
    behavioral_delta: Mapping[str, Any] | None,
    field_effect_confirmed: bool,
) -> AdoptionReceipt:
    operation = bundle.operation_plan[0]
    entries = operation.get("entries")
    if isinstance(entries, (str, bytes)) or not isinstance(entries, Sequence):
        raise HiveProtocolError("multi-program operation entries are invalid")
    _preflight_multi_program_entries(entries)
    predecessor_manifest = _digest(
        owner.checkpoints.current_manifest_sha256,
        "owner current manifest",
    )
    predecessor_state = _digest(owner.state.state_sha256, "owner current state")
    try:
        transaction = owner.begin_transaction()
    except AttributeError as exc:
        raise HiveProtocolError(
            "owner does not expose multi-program transactions"
        ) from exc
    receipts: list[AdoptionReceipt] = []
    try:
        for entry in entries:
            sub_bundle = replace(bundle, operation_plan=(dict(entry),))
            receipt = apply_bundle_to_owner(
                owner,
                sub_bundle,
                recipient_instance_id=recipient_instance_id,
                field_profile_sha256=field_profile_sha256,
                current_common_generation=current_common_generation,
                available_object_ids=available_object_ids,
                revoked_bundle_ids=revoked_bundle_ids,
                baseline_observation_ids=baseline_observation_ids,
                post_adoption_observation_ids=(),
                behavioral_delta=None,
                field_effect_confirmed=field_effect_confirmed,
            )
            if receipt.status not in {"accepted", "replayed"}:
                raise HiveProtocolError(
                    "multi-program bundle stopped after a non-admitted capability"
                )
            receipts.append(receipt)
    except BaseException:
        _rollback_multi_program_transaction(transaction)
        raise

    if all(receipt.status == "replayed" for receipt in receipts):
        try:
            result = admit_bundle(
                bundle,
                recipient_instance_id=recipient_instance_id,
                field_profile_sha256=field_profile_sha256,
                atlas_schema=ATLAS_SCHEMA,
                current_common_generation=current_common_generation,
                predecessor_manifest_sha256=predecessor_manifest,
                predecessor_state_sha256=predecessor_state,
                available_object_ids=available_object_ids,
                revoked_bundle_ids=revoked_bundle_ids,
                status="replayed",
                baseline_observation_ids=baseline_observation_ids,
                post_adoption_observation_ids=post_adoption_observation_ids,
                behavioral_delta=behavioral_delta,
                field_effect_confirmed=field_effect_confirmed,
            )
        except BaseException:
            _rollback_multi_program_transaction(transaction)
            raise
        transaction.commit()
        return result

    applied_object_ids: list[str] = []
    post_ids = list(post_adoption_observation_ids)
    capability_results: list[Mapping[str, Any]] = []
    for receipt in receipts:
        for object_id in receipt.applied_object_ids:
            if object_id not in applied_object_ids:
                applied_object_ids.append(object_id)
        post_ids.extend(receipt.post_adoption_observation_ids)
        capability_results.append(
            {
                "behavioral_delta": receipt.behavioral_delta,
                "object_ids": list(receipt.applied_object_ids),
                "post_adoption_observation_ids": list(
                    receipt.post_adoption_observation_ids
                ),
                "status": receipt.status,
            }
        )
    effective_behavioral_delta = dict(behavioral_delta or {})
    effective_behavioral_delta["capabilities"] = capability_results
    successor_manifest = _digest(
        owner.checkpoints.current_manifest_sha256,
        "owner multi-program successor manifest",
    )
    successor_state = _digest(
        owner.state.state_sha256,
        "owner multi-program successor state",
    )
    try:
        result = admit_bundle(
            bundle,
            recipient_instance_id=recipient_instance_id,
            field_profile_sha256=field_profile_sha256,
            atlas_schema=ATLAS_SCHEMA,
            current_common_generation=current_common_generation,
            predecessor_manifest_sha256=predecessor_manifest,
            predecessor_state_sha256=predecessor_state,
            successor_manifest_sha256=successor_manifest,
            successor_state_sha256=successor_state,
            available_object_ids=available_object_ids,
            revoked_bundle_ids=revoked_bundle_ids,
            applied_object_ids=tuple(applied_object_ids),
            baseline_observation_ids=baseline_observation_ids,
            post_adoption_observation_ids=tuple(post_ids),
            behavioral_delta=effective_behavioral_delta,
            field_effect_confirmed=field_effect_confirmed,
        )
    except BaseException:
        _rollback_multi_program_transaction(transaction)
        raise
    transaction.commit()
    return result


def apply_bundle_to_owner(
    owner: Any,
    bundle: KnowledgeBundle,
    *,
    recipient_instance_id: str,
    field_profile_sha256: str,
    current_common_generation: int,
    available_object_ids: Sequence[str] = (),
    revoked_bundle_ids: Sequence[str] = (),
    baseline_observation_ids: Sequence[str] = (),
    post_adoption_observation_ids: Sequence[str] = (),
    behavioral_delta: Mapping[str, Any] | None = None,
    field_effect_confirmed: bool = False,
) -> AdoptionReceipt:
    """Apply a semantically validated bundle through the real owner.

    Supported operations are ``configure-program``, ``promote-program``, and
    ``promote-programs``. Promotion bundles can carry replayable evidence and
    held-out witnesses; multi-program bundles aggregate the receipts from each
    capability.
    """

    if not isinstance(bundle, KnowledgeBundle):
        raise HiveProtocolError("bundle must be a KnowledgeBundle")
    if not hasattr(owner, "checkpoints") or not hasattr(owner, "state"):
        raise HiveProtocolError("owner does not expose checkpoint lineage")
    if (
        len(bundle.operation_plan) == 1
        and bundle.operation_plan[0].get("operation") == "promote-programs"
    ):
        return _apply_multi_program_bundle(
            owner,
            bundle,
            recipient_instance_id=recipient_instance_id,
            field_profile_sha256=field_profile_sha256,
            current_common_generation=current_common_generation,
            available_object_ids=available_object_ids,
            revoked_bundle_ids=revoked_bundle_ids,
            baseline_observation_ids=baseline_observation_ids,
            post_adoption_observation_ids=post_adoption_observation_ids,
            behavioral_delta=behavioral_delta,
            field_effect_confirmed=field_effect_confirmed,
        )
    predecessor_manifest = _digest(
        owner.checkpoints.current_manifest_sha256,
        "owner current manifest",
    )
    predecessor_state = _digest(owner.state.state_sha256, "owner current state")
    compatibility = bundle.compatibility
    dependencies = set(available_object_ids)

    def rejected(status: str = "incompatible") -> AdoptionReceipt:
        return admit_bundle(
            bundle,
            recipient_instance_id=recipient_instance_id,
            field_profile_sha256=field_profile_sha256,
            atlas_schema=ATLAS_SCHEMA,
            current_common_generation=current_common_generation,
            predecessor_manifest_sha256=predecessor_manifest,
            predecessor_state_sha256=predecessor_state,
            available_object_ids=tuple(dependencies),
            revoked_bundle_ids=revoked_bundle_ids,
            status=status,
            baseline_observation_ids=baseline_observation_ids,
            post_adoption_observation_ids=post_adoption_observation_ids,
            behavioral_delta=behavioral_delta,
            field_effect_confirmed=field_effect_confirmed,
        )

    if bundle.object_id in set(revoked_bundle_ids):
        return rejected("refused")
    if (
        field_profile_sha256 != compatibility["field_profile_sha256"]
        and not _portable_bundle_for_profile(bundle, field_profile_sha256)
    ):
        return rejected()
    if compatibility["atlas_schema"] != ATLAS_SCHEMA:
        return rejected()
    if current_common_generation != bundle.predecessor_common_generation:
        return rejected()
    if not set(bundle.dependencies).issubset(dependencies):
        return rejected()
    if len(bundle.operation_plan) != 1:
        return rejected()
    operation = bundle.operation_plan[0]
    operation_kind = operation.get("operation")
    if operation_kind not in {"configure-program", "promote-program"}:
        return rejected()
    program_payload = operation.get("program")
    if not isinstance(program_payload, Mapping):
        return rejected()
    try:
        program = FieldProgram.from_dict(program_payload)
    except Exception as exc:
        raise HiveProtocolError("bundle program cannot be decoded") from exc

    minimum_assessments: int | None = None
    maximum_average_loss: float | None = None
    bit_penalty: float | None = None
    replay_witness_mode = operation_kind == "promote-program" and (
        "support_witnesses" in operation or "assessment_witnesses" in operation
    )
    if operation_kind == "promote-program":
        raw_minimum = operation.get("minimum_assessments")
        raw_maximum = operation.get("maximum_average_loss")
        raw_penalty = operation.get("bit_penalty")
        if (
            isinstance(raw_minimum, bool)
            or not isinstance(raw_minimum, int)
            or raw_minimum < 1
            or isinstance(raw_maximum, bool)
            or not isinstance(raw_maximum, (int, float))
            or not math.isfinite(float(raw_maximum))
            or not 0 <= float(raw_maximum) <= 1
            or isinstance(raw_penalty, bool)
            or not isinstance(raw_penalty, (int, float))
            or not math.isfinite(float(raw_penalty))
            or float(raw_penalty) < 0
        ):
            return rejected("refused")
        minimum_assessments = raw_minimum
        maximum_average_loss = float(raw_maximum)
        bit_penalty = float(raw_penalty)

    def promotion_shape(value: Mapping[str, Any]) -> Mapping[str, Any]:
        shape = dict(value)
        for name in ("assessments", "status", "support_event_ids", "version"):
            shape.pop(name, None)
        return shape

    existing_program = next(
        (
            row
            for row in getattr(owner.state, "programs", ())
            if row.program_id == program.program_id
        ),
        None,
    )
    if operation_kind == "configure-program" and existing_program is not None:
        if existing_program.as_dict() == program.as_dict():
            return rejected("replayed")
        return rejected("refused")
    if operation_kind == "promote-program":
        if program.status != "candidate":
            return rejected("refused")
        if replay_witness_mode and program.assessments:
            return rejected("refused")
        if existing_program is not None:
            if existing_program.status == "promoted":
                if promotion_shape(existing_program.as_dict()) == promotion_shape(
                    program.as_dict()
                ):
                    return rejected("replayed")
                return rejected("refused")
            if replay_witness_mode:
                if promotion_shape(existing_program.as_dict()) != promotion_shape(
                    program.as_dict()
                ):
                    return rejected("refused")
            elif existing_program.as_dict() != program.as_dict():
                return rejected("refused")

    def parse_witnesses(
        name: str,
        *,
        assessment: bool,
        rows_override: Sequence[Any] | None = None,
    ) -> list[dict[str, Any]] | None:
        rows = operation.get(name, ()) if rows_override is None else rows_override
        if isinstance(rows, (str, bytes)) or not isinstance(rows, Sequence):
            return None
        parsed: list[dict[str, Any]] = []
        for row in rows:
            if not isinstance(row, Mapping):
                return None
            try:
                source_payload = dict(row["source"])
                if isinstance(source_payload.get("labels"), tuple):
                    source_payload["labels"] = list(source_payload["labels"])
                if isinstance(source_payload.get("span"), tuple):
                    source_payload["span"] = list(source_payload["span"])
                source = SourceInput.from_dict(source_payload)
            except Exception:
                return None
            values = row.get("values")
            context = row.get("context")
            if not isinstance(values, Mapping) or not isinstance(context, Mapping):
                return None
            for key, value in values.items():
                if (
                    not isinstance(key, str)
                    or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(float(value))
                ):
                    return None
            resolution_floor = row.get("resolution_floor")
            resolution_status = row.get("resolution_status")
            if resolution_floor is not None:
                if (
                    isinstance(resolution_floor, bool)
                    or not isinstance(resolution_floor, (int, float))
                    or not math.isfinite(float(resolution_floor))
                    or float(resolution_floor) < 0
                ):
                    return None
            if resolution_status is not None and resolution_status not in {
                "resolved",
                "unresolved",
            }:
                return None
            if resolution_status == "unresolved" and resolution_floor is None:
                return None
            if (
                assessment
                and name == "assessment_witnesses"
                and (resolution_status is None or resolution_floor is None)
            ):
                return None
            derivation_roots = row.get("derivation_roots", ())
            if (
                isinstance(derivation_roots, (str, bytes))
                or not isinstance(derivation_roots, Sequence)
            ):
                return None
            item: dict[str, Any] = {
                "context": dict(context),
                "derivation_roots": tuple(derivation_roots),
                "epistemic_type": row.get("epistemic_type", "observed"),
                "event_kind": row.get("event_kind", "observation"),
                "source": source,
                "values": dict(values),
            }
            if resolution_floor is not None:
                item["resolution_floor"] = float(resolution_floor)
            if resolution_status is not None:
                item["resolution_status"] = resolution_status
            if assessment:
                bindings = row.get("bindings")
                outcome = row.get("outcome")
                loss_scale = row.get("loss_scale")
                if (
                    not isinstance(bindings, Mapping)
                    or not isinstance(outcome, Mapping)
                    or isinstance(loss_scale, bool)
                    or not isinstance(loss_scale, (int, float))
                    or not math.isfinite(float(loss_scale))
                    or float(loss_scale) < 0
                ):
                    return None
                item["bindings"] = dict(bindings)
                item["outcome"] = dict(outcome)
                item["loss_scale"] = float(loss_scale)
            parsed.append(item)
        return parsed

    def parse_field_setup() -> tuple[list[VariableSpec], list[RelationChart]] | None:
        raw_variables = operation.get("variable_specs")
        raw_charts = operation.get("chart_specs")
        if (
            isinstance(raw_variables, (str, bytes))
            or not isinstance(raw_variables, Sequence)
            or isinstance(raw_charts, (str, bytes))
            or not isinstance(raw_charts, Sequence)
        ):
            return None
        variables: list[VariableSpec] = []
        charts: list[RelationChart] = []
        try:
            for row in raw_variables:
                if not isinstance(row, Mapping):
                    return None
                variables.append(VariableSpec.from_dict(dict(row)))
            for row in raw_charts:
                if not isinstance(row, Mapping):
                    return None
                charts.append(
                    RelationChart.empty(
                        chart_id=row["chart_id"],
                        scope=tuple(row["scope"]),
                        ridge=row["ridge"],
                        observation_norm_bound=row["observation_norm_bound"],
                        prior_mass=row["prior_mass"],
                    )
                )
        except Exception:
            return None
        return variables, charts

    support_witnesses: list[dict[str, Any]] = []
    assessment_witnesses: list[dict[str, Any]] = []
    held_out_witness: dict[str, Any] | None = None
    if "held_out_witness" in operation:
        if operation_kind not in {"promote-program", "configure-program"} or (
            operation_kind == "promote-program" and not replay_witness_mode
        ):
            return rejected("refused")
        parsed_held_out = parse_witnesses(
            "held_out_witness",
            assessment=True,
            rows_override=(operation.get("held_out_witness"),),
        )
        if parsed_held_out is None or len(parsed_held_out) != 1:
            return rejected("refused")
        held_out_witness = parsed_held_out[0]
    if replay_witness_mode:
        parsed_support = parse_witnesses("support_witnesses", assessment=False)
        parsed_assessment = parse_witnesses("assessment_witnesses", assessment=True)
        if parsed_support is None or parsed_assessment is None:
            return rejected("refused")
        if minimum_assessments is None or len(parsed_assessment) < minimum_assessments:
            return rejected("refused")
        support_witnesses = parsed_support
        assessment_witnesses = parsed_assessment
        field_setup = parse_field_setup()
        if field_setup is None:
            return rejected("refused")
        variables, charts = field_setup
        for index, variable in enumerate(variables):
            owner.configure_variable(
                f"hive:{bundle.object_id}:variable:{index}",
                variable,
            )
        for index, chart in enumerate(charts):
            existing = next(
                (
                    row
                    for row in owner.state.charts
                    if row.chart_id == chart.chart_id
                ),
                None,
            )
            if existing is not None and _chart_replay_semantically_matches(
                existing, chart
            ):
                continue
            owner.configure_chart(
                f"hive:{bundle.object_id}:chart:{index}",
                chart,
            )

    if replay_witness_mode:
        support_event_ids: list[str] = []
        for index, witness in enumerate(support_witnesses):
            admitted = owner.admit_observation(
                operation_id=f"hive:{bundle.object_id}:support:{index}",
                source=witness["source"],
                values=witness["values"],
                context=witness["context"],
                epistemic_type=witness["epistemic_type"],
                derivation_roots=witness["derivation_roots"],
                event_kind=witness["event_kind"],
            )
            support_event_ids.append(admitted["event"]["event_id"])
        recipient_payload = dict(program_payload)
        recipient_payload["support_event_ids"] = support_event_ids
        recipient_payload["assessments"] = []
        try:
            program = FieldProgram.from_dict(recipient_payload)
        except Exception as exc:
            raise HiveProtocolError("recipient candidate program is invalid") from exc

    configure_operation_id = f"hive:{bundle.object_id}:configure-program"
    configured = owner.configure_program(
        operation_id=configure_operation_id,
        program=program,
    )
    configured_receipt = (
        configured.as_dict() if hasattr(configured, "as_dict") else configured
    )
    if not isinstance(configured_receipt, Mapping):
        raise HiveProtocolError("owner program admission returned no receipt")
    if (
        operation_kind == "configure-program"
        and configured_receipt.get("replayed")
        and held_out_witness is not None
        and hasattr(owner, "evidence")
        and owner.evidence.event_for_operation(
            f"hive:{bundle.object_id}:held-out:observation"
        )
        is not None
    ):
        return rejected("replayed")
    held_out_result: dict[str, Any] | None = None
    held_out_event_id: str | None = None
    if operation_kind == "configure-program":
        raw_receipt = configured_receipt
        applied_program = program
    else:
        if replay_witness_mode:
            for index, witness in enumerate(assessment_witnesses):
                if witness.get("resolution_status") == "unresolved":
                    raise HiveProtocolError(
                        "cannot transfer an unresolved assessment"
                    )
                begun = owner.begin_program_assessment(
                    operation_id=f"hive:{bundle.object_id}:begin:{index}",
                    program_id=program.program_id,
                    bindings=witness["bindings"],
                )
                prediction_id = begun["prediction"]["prediction_id"]
                admitted = owner.admit_observation(
                    operation_id=f"hive:{bundle.object_id}:assessment:{index}",
                    source=witness["source"],
                    values=witness["values"],
                    context=witness["context"],
                    epistemic_type=witness["epistemic_type"],
                    derivation_roots=witness["derivation_roots"],
                    event_kind=witness["event_kind"],
                )
                resolved_assessment = owner.resolve_program_assessment(
                    operation_id=f"hive:{bundle.object_id}:resolve:{index}",
                    program_id=program.program_id,
                    prediction_id=prediction_id,
                    outcome=witness["outcome"],
                    event_id=admitted["event"]["event_id"],
                    loss_scale=witness["loss_scale"],
                )
                _verify_resolution_provenance(
                    witness,
                    resolved_assessment["assessment"],
                )
                _require_resolved_assessment(
                    resolved_assessment["assessment"],
                    "assessment",
                )
        promoted = owner.promote_program(
            operation_id=f"hive:{bundle.object_id}:promote-program",
            candidate_ids=(program.program_id,),
            minimum_assessments=minimum_assessments,
            maximum_average_loss=maximum_average_loss,
            bit_penalty=bit_penalty,
        )
        if not isinstance(promoted, Mapping):
            raise HiveProtocolError("owner program promotion returned no result")
        promoted_payload = promoted.get("program")
        raw_receipt = promoted.get("receipt")
        if not isinstance(promoted_payload, Mapping) or not isinstance(
            raw_receipt, Mapping
        ):
            raise HiveProtocolError("owner program promotion returned no receipt")
        try:
            applied_program = FieldProgram.from_dict(promoted_payload)
        except Exception as exc:
            raise HiveProtocolError("owner promotion returned an invalid program") from exc
    if held_out_witness is not None:
        if held_out_witness.get("resolution_status") == "unresolved":
            raise HiveProtocolError("cannot transfer an unresolved held-out assessment")
        begun = owner.begin_program_assessment(
            operation_id=f"hive:{bundle.object_id}:held-out:begin",
            program_id=program.program_id,
            bindings=held_out_witness["bindings"],
        )
        admitted = owner.admit_observation(
            operation_id=f"hive:{bundle.object_id}:held-out:observation",
            source=held_out_witness["source"],
            values=held_out_witness["values"],
            context=held_out_witness["context"],
            epistemic_type=held_out_witness["epistemic_type"],
            derivation_roots=held_out_witness["derivation_roots"],
            event_kind=held_out_witness["event_kind"],
        )
        resolved = owner.resolve_program_assessment(
            operation_id=f"hive:{bundle.object_id}:held-out:resolve",
            program_id=program.program_id,
            prediction_id=begun["prediction"]["prediction_id"],
            outcome=held_out_witness["outcome"],
            event_id=admitted["event"]["event_id"],
            loss_scale=held_out_witness["loss_scale"],
        )
        _verify_resolution_provenance(
            held_out_witness,
            resolved["assessment"],
        )
        _require_resolved_assessment(
            resolved["assessment"],
            "held-out assessment",
        )
        held_out_event_id = admitted["event"]["event_id"]
        held_out_result = {
            "assessment": resolved["assessment"],
            "prediction": begun["prediction"],
        }
    if raw_receipt.get("replayed"):
        return rejected("replayed")
    if held_out_result is not None:
        successor_manifest = _digest(
            owner.checkpoints.current_manifest_sha256,
            "owner held-out successor manifest",
        )
        successor_state = _digest(
            owner.state.state_sha256,
            "owner held-out successor state",
        )
    else:
        successor_manifest = _digest(raw_receipt["manifest_sha256"], "owner successor manifest")
        successor_state = _digest(raw_receipt["state_sha256"], "owner successor state")
    effective_post_adoption_ids = list(post_adoption_observation_ids)
    effective_behavioral_delta = dict(behavioral_delta or {})
    if held_out_result is not None and held_out_event_id is not None:
        assessment = held_out_result["assessment"]
        effective_post_adoption_ids.append(held_out_event_id)
        effective_behavioral_delta["held_out"] = {
            "assessment_id": assessment["assessment_id"],
            "normalized_loss": assessment["normalized_loss"],
            "outcome": assessment["outcome"],
            "prediction": held_out_result["prediction"]["predicted"],
            "resolution_floor": assessment["resolution_floor"],
            "resolution_status": assessment["resolution_status"],
        }
    return admit_bundle(
        bundle,
        recipient_instance_id=recipient_instance_id,
        field_profile_sha256=field_profile_sha256,
        atlas_schema=ATLAS_SCHEMA,
        current_common_generation=current_common_generation,
        predecessor_manifest_sha256=predecessor_manifest,
        predecessor_state_sha256=predecessor_state,
        successor_manifest_sha256=successor_manifest,
        successor_state_sha256=successor_state,
        available_object_ids=tuple(dependencies),
        revoked_bundle_ids=revoked_bundle_ids,
        applied_object_ids=(applied_program.program_id,),
        baseline_observation_ids=baseline_observation_ids,
        post_adoption_observation_ids=tuple(effective_post_adoption_ids),
        behavioral_delta=effective_behavioral_delta,
        field_effect_confirmed=field_effect_confirmed,
    )


def admit_bundle(
    bundle: KnowledgeBundle,
    *,
    recipient_instance_id: str,
    field_profile_sha256: str,
    atlas_schema: str,
    current_common_generation: int,
    predecessor_manifest_sha256: str,
    predecessor_state_sha256: str,
    successor_manifest_sha256: str | None = None,
    successor_state_sha256: str | None = None,
    available_object_ids: Sequence[str] = (),
    revoked_bundle_ids: Sequence[str] = (),
    status: str = "accepted",
    applied_object_ids: Sequence[str] = (),
    refused_object_ids: Sequence[str] = (),
    incompatible_object_ids: Sequence[str] = (),
    contradicted_object_ids: Sequence[str] = (),
    baseline_observation_ids: Sequence[str] = (),
    post_adoption_observation_ids: Sequence[str] = (),
    behavioral_delta: Mapping[str, Any] | None = None,
    field_effect_confirmed: bool = False,
) -> AdoptionReceipt:
    """Validate a recipient's bundle admission and publish its receipt contract.

    The actual field transition remains owner-owned. An accepted call therefore
    requires the successor digests produced by that real transition; rejected
    calls retain the predecessor state digest and cannot claim a successor.
    """

    if not isinstance(bundle, KnowledgeBundle):
        raise HiveProtocolError("bundle must be a KnowledgeBundle")
    _text(recipient_instance_id, "recipient instance id")
    _digest(field_profile_sha256, "recipient field profile")
    _text(atlas_schema, "recipient atlas schema")
    _nonnegative_int(current_common_generation, "current common generation")
    _digest(predecessor_manifest_sha256, "predecessor manifest")
    _digest(predecessor_state_sha256, "predecessor state")
    if status not in ADOPTION_STATUSES:
        raise HiveProtocolError("adoption status is unsupported")

    reason_status = status
    if bundle.object_id in set(revoked_bundle_ids):
        reason_status = "refused"
    elif (
        field_profile_sha256 != bundle.compatibility["field_profile_sha256"]
        and not _portable_bundle_for_profile(bundle, field_profile_sha256)
    ):
        reason_status = "incompatible"
    elif atlas_schema != bundle.compatibility["atlas_schema"]:
        reason_status = "incompatible"
    elif current_common_generation != bundle.predecessor_common_generation:
        reason_status = "incompatible"
    elif not set(bundle.dependencies).issubset(set(available_object_ids)):
        reason_status = "incompatible"

    if reason_status in {"accepted", "accepted-with-local-guard"}:
        if successor_manifest_sha256 is None or successor_state_sha256 is None:
            raise HiveProtocolError("accepted admission needs successor digests")
        _digest(successor_manifest_sha256, "successor manifest")
        _digest(successor_state_sha256, "successor state")
        if successor_state_sha256 == predecessor_state_sha256:
            raise HiveProtocolError("accepted admission must publish a successor state")
        applied = tuple(applied_object_ids)
        if not applied:
            raise HiveProtocolError("accepted admission needs applied object ids")
    else:
        successor_manifest_sha256 = predecessor_manifest_sha256
        successor_state_sha256 = predecessor_state_sha256
        applied = ()

    return AdoptionReceipt(
        hive_id=bundle.hive_id,
        bundle_id=bundle.object_id,
        recipient_instance_id=recipient_instance_id,
        predecessor_manifest_sha256=predecessor_manifest_sha256,
        predecessor_state_sha256=predecessor_state_sha256,
        successor_manifest_sha256=successor_manifest_sha256,
        successor_state_sha256=successor_state_sha256,
        expected_common_generation=bundle.predecessor_common_generation,
        resulting_common_generation=(
            bundle.resulting_common_generation
            if reason_status in {"accepted", "accepted-with-local-guard"}
            else current_common_generation
        ),
        status=reason_status,
        applied_object_ids=applied,
        refused_object_ids=tuple(refused_object_ids),
        incompatible_object_ids=tuple(incompatible_object_ids),
        contradicted_object_ids=tuple(contradicted_object_ids),
        baseline_observation_ids=tuple(baseline_observation_ids),
        post_adoption_observation_ids=tuple(post_adoption_observation_ids),
        behavioral_delta={} if behavioral_delta is None else behavioral_delta,
        field_effect_confirmed=field_effect_confirmed,
    )


def verify_object_digest(value: Mapping[str, Any]) -> bool:
    """Verify one serialized hive object's self-declared content digest."""

    if not isinstance(value, Mapping):
        return False
    schema = value.get("schema")
    content = value.get("content")
    declared = value.get("content_sha256")
    object_id = value.get("object_id")
    if not isinstance(schema, str) or not isinstance(content, Mapping):
        return False
    if not isinstance(declared, str) or declared != object_id:
        return False
    try:
        return declared == _digest_content(schema, content)
    except (HiveProtocolError, TypeError, ValueError):
        return False


__all__ = [
    "ADOPTION_SCHEMA",
    "ADOPTION_STATUSES",
    "ATLAS_SCHEMA",
    "BUNDLE_SCHEMA",
    "CANDIDATE_KINDS",
    "ExperienceCandidate",
    "ExperienceCapsule",
    "ExperienceEpisode",
    "ExperienceEvidence",
    "ExperienceOrigin",
    "HiveProtocolError",
    "PORTABLE_PROFILE_SHA256",
    "PORTABLE_TRANSFER_SCHEMA",
    "KnowledgeBundle",
    "REVIEW_RESULTS",
    "REVIEW_TYPES",
    "REPRESENTATION_SCHEMA",
    "Review",
    "TransferSpec",
    "AdoptionReceipt",
    "build_knowledge_bundle",
    "admit_bundle",
    "apply_bundle_to_owner",
    "capsule_from_owner_transition",
    "verify_object_digest",
]
