"""Persistent leader and deterministic reviewer paths for Cassi Hive."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Any, Mapping, Sequence

from cassi_field_atlas import sha256_value
from cassi_field_hive import Review
from cassi_hive_collective import (
    CollectiveHive,
    InstanceIdentity,
    ReviewerProfile,
)
from cassi_hive_coordinator import HiveCoordinator, HiveCoordinatorError
from cassi_hive_store import LocalHiveStore

PROMOTION_SCHEMA = "cassifi.hive.promotion.v1"


@dataclass(frozen=True, slots=True)
class ReviewerDecision:
    """One explicit reviewer verdict for one candidate group."""

    reviewer_instance_id: str
    result: str
    review_type: str = "transfer-review"
    evidence_ids: tuple[str, ...] = ()
    rationale: str = ""

    def __post_init__(self) -> None:
        if not self.reviewer_instance_id:
            raise ValueError("reviewer_instance_id must be nonempty")
        if self.result not in {"supports", "refutes", "inconclusive"}:
            raise ValueError("review result is unsupported")
        if self.review_type not in {"independent-reproduction", "adversarial-review", "transfer-review"}:
            raise ValueError("review type is unsupported")
        if any(not isinstance(item, str) or not item for item in self.evidence_ids):
            raise ValueError("review evidence IDs must be nonempty text")


@dataclass(frozen=True, slots=True)
class PromotionReport:
    """One idempotent leader-loop pass."""

    scanned_candidate_ids: tuple[str, ...] = ()
    eligible_candidate_ids: tuple[str, ...] = ()
    promoted_bundle_ids: tuple[str, ...] = ()
    skipped_candidate_ids: tuple[str, ...] = ()
    errors: tuple[Mapping[str, Any], ...] = ()

    @property
    def schema(self) -> str:
        return PROMOTION_SCHEMA

    def as_dict(self) -> Mapping[str, Any]:
        return {
            "eligible_candidate_ids": list(self.eligible_candidate_ids),
            "errors": [dict(item) for item in self.errors],
            "promoted_bundle_ids": list(self.promoted_bundle_ids),
            "scanned_candidate_ids": list(self.scanned_candidate_ids),
            "schema": PROMOTION_SCHEMA,
            "skipped_candidate_ids": list(self.skipped_candidate_ids),
        }


class DeterministicReviewer:
    """Persist an explicit, reproducible reviewer decision.

    This class does not infer scientific support.  The caller supplies the
    verdict; the reviewer binds it to the exact candidate and source capsules
    currently present in the hive, making the admission path reproducible.
    """

    def __init__(self, coordinator: HiveCoordinator, reviewer_instance_id: str) -> None:
        if not isinstance(coordinator, HiveCoordinator):
            raise ValueError("reviewer requires a HiveCoordinator")
        if not reviewer_instance_id:
            raise ValueError("reviewer_instance_id must be nonempty")
        self.coordinator = coordinator
        self.reviewer_instance_id = reviewer_instance_id

    def admit(self, candidate_id: str, decision: ReviewerDecision) -> str:
        if decision.reviewer_instance_id != self.reviewer_instance_id:
            raise ValueError("decision reviewer does not match this reviewer")
        group = next(
            (item for item in self.coordinator.groups() if item.candidate_id == candidate_id),
            None,
        )
        if group is None:
            raise HiveCoordinatorError("candidate group is unavailable")
        evidence_ids = decision.evidence_ids or tuple(
            sorted(
                {
                    *(
                        event_id
                        for capsule in group.capsules
                        for event_id in capsule.evidence.support_event_ids
                    ),
                    *(
                        assessment_id
                        for capsule in group.capsules
                        for assessment_id in capsule.evidence.assessment_ids
                    ),
                }
            )
        )
        if not evidence_ids:
            evidence_ids = (sha256_value({"candidate_id": candidate_id}),)
        review = Review(
            reviewer_instance_id=self.reviewer_instance_id,
            review_type=decision.review_type,
            result=decision.result,
            evidence_ids=evidence_ids,
        )
        return self.coordinator.review(
            review,
            candidate_id=candidate_id,
            source_experience_ids=tuple(capsule.object_id for capsule in group.capsules),
        )

class PromotionLoop:
    """Leader-side promotion loop with optional weighted collective quorum."""

    def __init__(
        self,
        store: LocalHiveStore,
        *,
        leader_instance_id: str,
        minimum_support_reviews: int = 2,
        collective: CollectiveHive | None = None,
        reviewer_profiles: Mapping[str, ReviewerProfile] | None = None,
        reviewer_identities: Mapping[str, InstanceIdentity] | None = None,
        minimum_support_weight: float | None = None,
        minimum_independent_reviewers: int | None = None,
    ) -> None:
        if not isinstance(store, LocalHiveStore):
            raise ValueError("promotion loop requires a LocalHiveStore")
        if not leader_instance_id:
            raise ValueError("leader_instance_id must be nonempty")
        if isinstance(minimum_support_reviews, bool) or minimum_support_reviews < 1:
            raise ValueError("minimum_support_reviews must be positive")
        self.store = store
        self.coordinator = HiveCoordinator(store, leader_instance_id=leader_instance_id)
        self.minimum_support_reviews = minimum_support_reviews
        self.collective = collective
        self.reviewer_profiles = dict(reviewer_profiles or {})
        self.reviewer_identities = dict(reviewer_identities or {})
        self.minimum_support_weight = minimum_support_weight
        self.minimum_independent_reviewers = minimum_independent_reviewers

    def review(self, candidate_id: str, decisions: Sequence[ReviewerDecision]) -> tuple[str, ...]:
        reviewer_ids: set[str] = set()
        review_ids: list[str] = []
        for decision in decisions:
            if decision.reviewer_instance_id in reviewer_ids:
                raise HiveCoordinatorError("candidate reviews need distinct reviewer instances")
            reviewer_ids.add(decision.reviewer_instance_id)
            review_ids.append(
                DeterministicReviewer(self.coordinator, decision.reviewer_instance_id).admit(
                    candidate_id,
                    decision,
                )
            )
        return tuple(review_ids)

    def refresh_reviewer_profiles(self) -> Mapping[str, ReviewerProfile]:
        """Reload persisted reviewer calibration before a later promotion pass."""
        if self.collective is None:
            return dict(self.reviewer_profiles)
        for reviewer_id in tuple(self.reviewer_profiles):
            profile = self.collective.reputation.load(reviewer_id)
            if profile is not None:
                self.reviewer_profiles[reviewer_id] = profile
        return dict(self.reviewer_profiles)

    def run_once(self) -> PromotionReport:
        self.refresh_reviewer_profiles()
        groups = self.coordinator.groups()
        scanned = tuple(group.candidate_id for group in groups)
        published_sources = {
            source_id
            for bundle in self.store.list_bundles()
            for source_id in bundle.source_experience_ids
        }
        eligible: list[str] = []
        promoted: list[str] = []
        skipped: list[str] = []
        errors: list[Mapping[str, Any]] = []
        for group in groups:
            operation_plan = group.capsules[0].candidate.operation_plan
            if (
                len(operation_plan) != 1
                or operation_plan[0].get("operation")
                not in {"configure-program", "promote-program"}
            ):
                skipped.append(group.candidate_id)
                continue
            if all(capsule.object_id in published_sources for capsule in group.capsules):
                skipped.append(group.candidate_id)
                continue
            reviews = self.store.list_reviews(candidate_object_id=group.candidate_id)
            support_count = sum(review.result == "supports" for review in reviews)
            if self.collective is not None and self.minimum_support_weight is not None:
                quorum = self.collective.weighted_quorum(
                    reviews,
                    self.reviewer_profiles,
                    self.reviewer_identities,
                    origin_instance_ids=tuple(
                        capsule.origin.instance_id for capsule in group.capsules
                    ),
                    minimum_support_weight=self.minimum_support_weight,
                    minimum_independent_reviewers=(
                        self.minimum_independent_reviewers
                        if self.minimum_independent_reviewers is not None
                        else self.minimum_support_reviews
                    ),
                )
                if not quorum.accepted:
                    skipped.append(group.candidate_id)
                    errors.append(
                        {
                            "candidate_id": group.candidate_id,
                            "code": "WEIGHTED_QUORUM_REJECTED",
                            "quorum": quorum.as_dict(),
                        }
                    )
                    continue
            elif support_count < self.minimum_support_reviews or any(
                review.result == "refutes" for review in reviews
            ):
                skipped.append(group.candidate_id)
                continue
            eligible.append(group.candidate_id)
            try:
                bundle = self.coordinator.promote(
                    candidate_id=group.candidate_id,
                    reviews=reviews,
                    minimum_support_reviews=self.minimum_support_reviews,
                )
            except HiveCoordinatorError as exc:
                errors.append(
                    {
                        "candidate_id": group.candidate_id,
                        "error": str(exc),
                        "code": type(exc).__name__,
                    }
                )
            else:
                promoted.append(bundle.object_id)
        return PromotionReport(
            scanned_candidate_ids=scanned,
            eligible_candidate_ids=tuple(eligible),
            promoted_bundle_ids=tuple(promoted),
            skipped_candidate_ids=tuple(skipped),
            errors=tuple(errors),
        )

    def run_forever(self, stop_event: threading.Event, *, interval_seconds: float = 1.0) -> None:
        if interval_seconds <= 0:
            raise ValueError("interval_seconds must be positive")
        while not stop_event.is_set():
            self.run_once()
            stop_event.wait(interval_seconds)


__all__ = [
    "DeterministicReviewer",
    "PROMOTION_SCHEMA",
    "PromotionLoop",
    "PromotionReport",
    "ReviewerDecision",
]
