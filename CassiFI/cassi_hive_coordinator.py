"""Coordination and promotion operations for Cassi Hive."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cassi_field_atlas import sha256_value
from cassi_field_hive import (
    ExperienceCapsule,
    HiveProtocolError,
    KnowledgeBundle,
    Review,
    build_knowledge_bundle,
)
from cassi_hive_store import HiveStoreError, LocalHiveStore


COORDINATOR_SCHEMA = "cassifi.hive.coordinator.v1"


class HiveCoordinatorError(RuntimeError):
    """Raised when collection, review, or promotion cannot proceed."""


@dataclass(frozen=True, slots=True)
class CandidateGroup:
    """Compatible capsules that can be considered as one skill revision."""

    candidate_id: str
    capsules: tuple[ExperienceCapsule, ...]

    @property
    def hive_id(self) -> str:
        return self.capsules[0].hive_id

    @property
    def field_profile_sha256(self) -> str:
        return self.capsules[0].origin.field_profile_sha256

    @property
    def candidate_kind(self) -> str:
        return self.capsules[0].candidate.kind


class HiveCoordinator:
    """Leader-side control plane over a ``LocalHiveStore``.

    The coordinator never mutates a recipient field.  It only stores capsules,
    records reviews, promotes a reviewed bundle, and advances the shared hive
    generation atomically.
    """

    def __init__(
        self,
        store: LocalHiveStore,
        *,
        leader_instance_id: str,
        authority_grant_sha256: str | None = None,
    ) -> None:
        if not isinstance(store, LocalHiveStore):
            raise HiveCoordinatorError("coordinator requires a LocalHiveStore")
        if not isinstance(leader_instance_id, str) or not leader_instance_id:
            raise HiveCoordinatorError("leader_instance_id must be nonempty text")
        self.store = store
        self.leader_instance_id = leader_instance_id
        self.authority_grant_sha256 = authority_grant_sha256 or sha256_value(
            {
                "branch": store.branch,
                "hive_id": store.hive_id,
                "leader_instance_id": leader_instance_id,
                "schema": "cassifi.hive.local-authority.v1",
            }
        )

    @staticmethod
    def _candidate_id(capsule: ExperienceCapsule) -> str:
        portable = (
            capsule.candidate.kind == "field-program"
            and capsule.candidate.object.get("portable_transfer") is True
        )
        return sha256_value(
            {
                "candidate": capsule.candidate.as_dict(),
                "field_profile_sha256": "portable" if portable else capsule.origin.field_profile_sha256,
            }
        )

    def collect(self, capsule: ExperienceCapsule) -> str:
        if not isinstance(capsule, ExperienceCapsule):
            raise HiveCoordinatorError("collect requires an ExperienceCapsule")
        if capsule.hive_id != self.store.hive_id:
            raise HiveCoordinatorError("capsule belongs to another hive")
        return self.store.put_capsule(capsule)

    def collect_many(self, capsules: Sequence[ExperienceCapsule]) -> tuple[str, ...]:
        return tuple(self.collect(capsule) for capsule in capsules)

    def groups(self) -> tuple[CandidateGroup, ...]:
        groups: dict[str, list[ExperienceCapsule]] = {}
        for capsule in self.store.list_capsules(hive_id=self.store.hive_id):
            groups.setdefault(self._candidate_id(capsule), []).append(capsule)
        return tuple(
            CandidateGroup(candidate_id=key, capsules=tuple(value))
            for key, value in sorted(groups.items())
        )

    def review(
        self,
        review: Review,
        *,
        candidate_id: str,
        source_experience_ids: Sequence[str] = (),
    ) -> str:
        if not isinstance(review, Review):
            raise HiveCoordinatorError("review requires a Review")
        try:
            return self.store.put_review(
                review,
                candidate_object_id=candidate_id,
                source_experience_ids=source_experience_ids,
            )
        except HiveStoreError as exc:
            raise HiveCoordinatorError(str(exc)) from exc

    def promote(
        self,
        *,
        candidate_id: str | None = None,
        capsules: Sequence[ExperienceCapsule] | None = None,
        reviews: Sequence[Review] | None = None,
        minimum_support_reviews: int = 2,
    ) -> KnowledgeBundle:
        if candidate_id is not None:
            groups = [group for group in self.groups() if group.candidate_id == candidate_id]
            if not groups:
                raise HiveCoordinatorError("candidate group is unavailable")
            if capsules is not None:
                raise HiveCoordinatorError("provide candidate_id or capsules, not both")
            selected_capsules = groups[0].capsules
            selected_candidate_id = candidate_id
        elif capsules is not None:
            selected_capsules = tuple(capsules)
            if not selected_capsules:
                raise HiveCoordinatorError("promotion requires at least one capsule")
            selected_candidate_id = self._candidate_id(selected_capsules[0])
        else:
            groups = self.groups()
            if len(groups) != 1:
                raise HiveCoordinatorError("promotion without a candidate_id requires exactly one candidate group")
            selected_capsules = groups[0].capsules
            selected_candidate_id = groups[0].candidate_id

        for capsule in selected_capsules:
            self.collect(capsule)
        selected_reviews = tuple(reviews) if reviews is not None else self.store.list_reviews(candidate_object_id=selected_candidate_id)
        try:
            bundle = build_knowledge_bundle(
                selected_capsules,
                leader_instance_id=self.leader_instance_id,
                authority_grant_sha256=self.authority_grant_sha256,
                predecessor_common_generation=self.store.current_generation,
                reviews=selected_reviews,
                minimum_support_reviews=minimum_support_reviews,
            )
            self.store.publish_bundle(bundle, expected_generation=self.store.current_generation)
        except (HiveProtocolError, HiveStoreError) as exc:
            raise HiveCoordinatorError(str(exc)) from exc
        return bundle

    def revoke(self, bundle_id: str, *, reason: str) -> str:
        try:
            return self.store.revoke_bundle(bundle_id, reason=reason, actor=self.leader_instance_id)
        except HiveStoreError as exc:
            raise HiveCoordinatorError(str(exc)) from exc

    def status(self) -> Mapping[str, Any]:
        return {
            "authority_grant_sha256": self.authority_grant_sha256,
            "candidate_groups": len(self.groups()),
            "hive": self.store.status(),
            "leader_instance_id": self.leader_instance_id,
            "schema": COORDINATOR_SCHEMA,
        }


__all__ = ["COORDINATOR_SCHEMA", "CandidateGroup", "HiveCoordinator", "HiveCoordinatorError"]
