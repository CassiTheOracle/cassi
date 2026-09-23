from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cassi_field_atlas import FieldProgram, PrimitiveStep
from cassi_hive_coordinator import HiveCoordinator
from cassi_hive_collective import (
    ExecutionAssessment,
    OutcomeMetric,
    OUTCOME_SCHEMA,
    POPULATION_ROLLOUT_SCHEMA,
    POPULATION_ROUNDS_SCHEMA,
    ReviewerProfile,
)
from cassi_field_hive import Review
from cassi_hive_promotion import PromotionLoop
from cassi_hive_rollout import (
    MemberRolloutSpec,
    MultiRoundPopulationRollout,
    PopulationRollout,
    PopulationRolloutError,
    PopulationRoundSpec,
)
from cassi_hive_runtime import HiveField
from cassi_hive_store import LocalHiveStore, make_document


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def program(program_id: str = "population-program") -> FieldProgram:
    return FieldProgram(
        program_id=program_id,
        version=1,
        roles=("source",),
        steps=(PrimitiveStep(operation="identity", output="result", inputs=("source",)),),
        outputs=("result",),
    )


def promote_bundle(root: Path, program_id: str = "population-program") -> str:
    with HiveField.open(
        root / "scout",
        hive_home=root / "hive",
        hive_id="population-hive",
        instance_id="scout",
        mode="scout",
    ) as scout:
        scout.owner.configure_program(f"scout:configure:{program_id}", program(program_id))
    with LocalHiveStore(root / "hive", hive_id="population-hive") as store:
        coordinator = HiveCoordinator(store, leader_instance_id="leader")
        group = next(
            group
            for group in coordinator.groups()
            if group.capsules[0].candidate.object.get("program", {}).get("program_id") == program_id
        )
        for reviewer in ("reviewer-a", "reviewer-b"):
            coordinator.review(
                Review(
                    reviewer_instance_id=reviewer,
                    review_type="independent-reproduction",
                    result="supports",
                    evidence_ids=(digest(f"{reviewer}:{program_id}"),),
                ),
                candidate_id=group.candidate_id,
            )
        return coordinator.promote(candidate_id=group.candidate_id).object_id


def specs(
    root: Path,
    store: LocalHiveStore,
    bundle_id: str,
    protocol_sha256: str,
    posts: tuple[float, ...] = (0.8, 0.75, 0.9),
) -> tuple[MemberRolloutSpec, ...]:
    result: list[MemberRolloutSpec] = []
    for index, post in enumerate(posts, start=1):
        instance_id = f"member-{index}"
        field_home = root / "fields" / instance_id
        profile = digest(f"profile:{index}")
        with HiveField.open(
            field_home,
            hive=store,
            hive_id="population-hive",
            instance_id=instance_id,
            role="member",
            mode="member",
            apply_mode="verified",
            sync_mode="manual",
            profile_sha256=profile,
        ) as member:
            adoption = member.adopt(bundle_ids=(bundle_id,))
            assert bundle_id in adoption.applied or bundle_id in adoption.replayed
            receipt_document = next(
                document
                for document in reversed(
                    store.list_adoptions(instance_id=instance_id)
                )
                if document["content"]["bundle_id"] == bundle_id
            )
            trace_id = store.put_document(
                make_document(
                    "cassifi.hive.execution-trace.v1",
                    {
                        "bundle_id": bundle_id,
                        "instance_id": instance_id,
                        "rows": [{"baseline": 0.5, "post": post}],
                    },
                )
            )
            assessment = ExecutionAssessment(
                bundle_id=bundle_id,
                recipient_instance_id=instance_id,
                adoption_receipt_id=receipt_document["object_id"],
                protocol_sha256=protocol_sha256,
                evaluator_id="test-fixed-evaluator",
                evaluator_version="1",
                trace_document_ids=(trace_id,),
                metrics=(
                    OutcomeMetric(
                        "held_out_accuracy",
                        0.5,
                        1.0,
                        post,
                    ),
                ),
                held_out=True,
                scoring_rule="fixed-trace-accuracy-v1",
                observed_ns=index,
                valid_until_ns=10_000,
            )
            member.collective.record_execution_assessment(assessment)
        result.append(
            MemberRolloutSpec(
                instance_id=instance_id,
                field_home=field_home,
                field_profile_sha256=profile,
                assessment_id=assessment.object_id,
            )
        )
    return tuple(result)


def test_population_rollout_adopts_one_bundle_in_distinct_live_members() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        bundle_id = promote_bundle(root)
        with LocalHiveStore(root / "hive", hive_id="population-hive") as store:
            ledger = PopulationRollout(
                store,
                hive_id="population-hive",
            ).run(
                bundle_id,
                protocol_sha256=digest("population-protocol"),
                members=specs(
                    root,
                    store,
                    bundle_id,
                    digest("population-protocol"),
                ),
                created_ns=99,
            )
            assert ledger.status == "accepted"
            assert ledger.member_count == 3
            assert ledger.adopted_count == 3
            assert ledger.successful_outcome_count == 3
            assert ledger.failed_adoption_count == 0
            assert ledger.outcome_coverage == 1.0
            assert ledger.population_score > 0.5
            assert len({member.field_profile_sha256 for member in ledger.members}) == 3
            assert all(member.adoption_status == "accepted" for member in ledger.members)
            assert all(member.outcome_success for member in ledger.members)
            assert all("population-program" in member.adopted_program_ids for member in ledger.members)
            assert store.has_object(ledger.object_id)
            ledgers = store.list_documents(schema=POPULATION_ROLLOUT_SCHEMA)
            outcomes = store.list_documents(schema=OUTCOME_SCHEMA)
            assert [document["object_id"] for document in ledgers] == [ledger.object_id]
            assert len(outcomes) == 3


def test_successive_rounds_compare_members_and_calibrate_future_promotion() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        bundle_one = promote_bundle(root)
        profiles = {
            reviewer_id: ReviewerProfile.virgin(
                reviewer_id,
                digest(f"{reviewer_id}:key"),
            )
            for reviewer_id in ("reviewer-a", "reviewer-b")
        }
        with LocalHiveStore(root / "hive", hive_id="population-hive") as store:
            runner = MultiRoundPopulationRollout(
                store,
                hive_id="population-hive",
                reviewer_profiles=profiles,
            )
            first = runner.run_round(
                PopulationRoundSpec(
                    bundle_id=bundle_one,
                    protocol_sha256=digest("population-protocol:v1"),
                    members=specs(
                        root,
                        store,
                        bundle_one,
                        digest("population-protocol:v1"),
                        (0.8, 0.75, 0.9),
                    ),
                    reviewer_predictions={"reviewer-a": 0.9, "reviewer-b": 0.8},
                    independent_reviewer_ids=("reviewer-a", "reviewer-b"),
                )
            )
            assert first.status == "accepted"
            assert first.calibrated_reviewer_ids == ("reviewer-a", "reviewer-b")
            assert all(item.population_score is not None for item in first.comparisons)
            with HiveField.open(
                root / "scout",
                hive=store,
                hive_id="population-hive",
                instance_id="scout",
                mode="scout",
            ) as scout:
                scout.owner.configure_program(
                    "scout:configure:population-program-v2",
                    program("population-program-v2"),
                )
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = next(
                group
                for group in coordinator.groups()
                if group.capsules[0].candidate.object.get("program", {}).get("program_id")
                == "population-program-v2"
            )
            for reviewer in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(f"{reviewer}:population-program-v2"),),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle_two = coordinator.promote(candidate_id=group.candidate_id).object_id
            second = runner.run_round(
                PopulationRoundSpec(
                    bundle_id=bundle_two,
                    protocol_sha256=digest("population-protocol:v2"),
                    members=specs(
                        root,
                        store,
                        bundle_two,
                        digest("population-protocol:v2"),
                        (0.9, 0.8, 0.95),
                    ),
                    reviewer_predictions={"reviewer-a": 0.95, "reviewer-b": 0.85},
                    independent_reviewer_ids=("reviewer-a", "reviewer-b"),
                )
            )
            assert second.round_index == 1
            assert second.status == "accepted"
            assert all(item.local_score_delta is not None for item in second.comparisons)
            assert all(item.population_score_delta is not None for item in second.comparisons)
            assert all(item.local_minus_population is not None for item in second.comparisons)
            rounds = runner.finalize(created_ns=123)
            assert rounds.status == "accepted"
            assert rounds.round_count == 2
            assert store.has_object(rounds.object_id)
            assert len(store.list_documents(schema=POPULATION_ROUNDS_SCHEMA)) == 1
            promotion = PromotionLoop(
                store,
                leader_instance_id="leader",
                collective=runner.collective,
                reviewer_profiles=profiles,
            )
            refreshed = promotion.refresh_reviewer_profiles()
            assert refreshed["reviewer-a"].review_count == 2
            assert refreshed["reviewer-b"].review_count == 2


def test_population_rollout_rejects_duplicate_profiles_before_opening_members() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with LocalHiveStore(root / "hive", hive_id="population-hive") as store:
            member_specs = (
                MemberRolloutSpec(
                    instance_id="member-a",
                    field_home=root / "fields" / "a",
                    field_profile_sha256=digest("same-profile"),
                    assessment_id=digest("assessment-a"),
                ),
                MemberRolloutSpec(
                    instance_id="member-b",
                    field_home=root / "fields" / "b",
                    field_profile_sha256=digest("same-profile"),
                    assessment_id=digest("assessment-b"),
                ),
            )
            with pytest.raises(PopulationRolloutError, match="profiles must be distinct"):
                PopulationRollout(store, hive_id="population-hive").run(
                    digest("bundle"),
                    protocol_sha256=digest("protocol"),
                    members=member_specs,
                )
            assert store.list_documents(schema=POPULATION_ROLLOUT_SCHEMA) == ()
