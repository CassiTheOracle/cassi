"""Run a bounded end-to-end Cassi Hive collective improvement campaign.

The campaign exercises identity attestation, reviewer independence and weighted
quorum, branch-preserving hypotheses, demand routing, diversity selection,
specialist assignment, typed program composition, adaptation forks, outcome
calibration, memory consolidation, and the semantic bridge.  It is deliberately
self-contained: no adaptive field tensor is serialized and no remote endpoint
is contacted unless a caller explicitly replaces the bridge sink.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Mapping

from cassi_field_atlas import FieldProgram, PrimitiveStep, sha256_value
from cassi_field_hive import (
    ExperienceCandidate,
    ExperienceEpisode,
    ExperienceCapsule,
    ExperienceEvidence,
    ExperienceOrigin,
    TransferSpec,
)
from cassi_hive_bridge import SemanticEventBridge
from cassi_hive_collective import (
    CollectiveHive,
    ExecutionAssessment,
    DiversityProfile,
    DiversitySelector,
    HiveOffer,
    HiveQuery,
    HypothesisEdge,
    InstanceIdentity,
    OutcomeMetric,
    ReviewerProfile,
    RoleAssignment,
    compose_field_programs,
)
from cassi_hive_promotion import PromotionLoop, ReviewerDecision
from cassi_hive_rollout import (
    MemberRolloutSpec,
    MultiRoundPopulationRollout,
    PopulationRoundSpec,
)
from cassi_hive_store import LocalHiveStore, make_document

from cassi_hive_runtime import HiveField
ATLAS_SCHEMA = "cassifi.field-atlas.v2"


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()
def measured_rollout_specs(
    store: LocalHiveStore,
    root: Path,
    *,
    bundle_id: str,
    protocol_sha256: str,
    posts: tuple[float, ...],
    observed_offset: int,
    prior: tuple[MemberRolloutSpec, ...] | None = None,
) -> tuple[MemberRolloutSpec, ...]:
    specifications: list[MemberRolloutSpec] = []
    for index, post in enumerate(posts, start=1):
        instance_id = f"member-{index}"
        field_home = (
            root / instance_id
            if prior is None
            else prior[index - 1].field_home
        )
        profile = (
            digest(f"{instance_id}-profile")
            if prior is None
            else prior[index - 1].field_profile_sha256
        )
        with HiveField.open(
            field_home,
            hive=store,
            hive_id="campaign-hive",
            instance_id=instance_id,
            role="member",
            mode="member",
            apply_mode="verified",
            sync_mode="manual",
            profile_sha256=profile,
        ) as member:
            adoption = member.adopt(bundle_ids=(bundle_id,))
            if bundle_id not in adoption.applied and bundle_id not in adoption.replayed:
                raise RuntimeError("campaign member adoption did not complete")
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
                evaluator_id="campaign-fixed-evaluator",
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
                scoring_rule="campaign-trace-accuracy-v1",
                observed_ns=observed_offset + index,
                valid_until_ns=observed_offset + 10_000,
            )
            member.collective.record_execution_assessment(assessment)
        specifications.append(
            MemberRolloutSpec(
                instance_id=instance_id,
                field_home=field_home,
                field_profile_sha256=profile,
                assessment_id=assessment.object_id,
            )
        )
    return tuple(specifications)




def identity(name: str, *, parent: str | None = None) -> InstanceIdentity:
    return InstanceIdentity.issue(
        instance_id=name,
        secret=(name + "-campaign-secret").encode("utf-8"),
        source_identity_sha256=digest(name + ":source"),
        configuration_sha256=digest(name + ":config"),
        parent_instance_id=parent,
        issued_ns=1,
    )


def make_capsule(
    *,
    instance_id: str,
    field_profile: str,
    program: FieldProgram,
    branch: str,
) -> ExperienceCapsule:
    """Build one bounded semantic experience with two held-out witnesses."""

    return ExperienceCapsule(
        hive_id="campaign-hive",
        origin=ExperienceOrigin(
            instance_id=instance_id,
            role="scout",
            field_profile_sha256=field_profile,
            atlas_schema=ATLAS_SCHEMA,
            predecessor_manifest_sha256=digest(instance_id + ":manifest:0"),
            predecessor_state_sha256=digest(instance_id + ":state:0"),
            successor_manifest_sha256=digest(instance_id + ":manifest:1"),
            successor_state_sha256=digest(instance_id + ":state:1"),
            local_generation=1,
            common_generation=0,
        ),
        episode=ExperienceEpisode(
            task_id="campaign-task",
            context={"domain": "reasoning", "branch": branch},
            source_revision_ids=(digest("campaign-source"),),
            observation_event_ids=(digest(instance_id + ":observation"),),
            action={"operation": "configure-program", "program_id": program.program_id},
            prediction={"held_out_gain": 0.25},
            outcome={"held_out_gain": 0.25, "status": "improved"},
            work_units=4,
            uncertainty=0.1,
        ),
        candidate=ExperienceCandidate(
            kind="field-program",
            object={
                "portable_transfer": True,
                "program": dict(program.as_dict()),
                "program_id": program.program_id,
                "program_version": program.version,
                "program_roles": list(program.roles),
                "program_sha256": sha256_value(program.as_dict()),
            },
            operation_plan=(
                {
                    "operation": "configure-program",
                    "program": dict(program.as_dict()),
                    "program_id": program.program_id,
                },
            ),
            guards=({"field": "held_out", "operator": "equals", "value": True},),
            dependencies=(),
        ),
        evidence=ExperienceEvidence(
            support_event_ids=(digest(instance_id + ":observation"),),
            assessment_ids=(digest(instance_id + ":assessment"),),
            held_out_results=(
                {"split": "held-out-a", "baseline": 0.5, "control": 0.5, "post": 0.8},
                {"split": "held-out-b", "baseline": 0.4, "control": 0.4, "post": 0.7},
            ),
            counterexamples=(),
            derivation_roots=(digest("campaign-derivation"),),
        ),
        transfer=TransferSpec(
            required_field_profile_sha256=field_profile,
            required_atlas_schema=ATLAS_SCHEMA,
            replay_mode="semantic",
            maximum_admission_work=32,
            visibility="public",
        ),
    )


def run_campaign(root: Path) -> Mapping[str, Any]:
    with LocalHiveStore(root, hive_id="campaign-hive") as store:
        collective = CollectiveHive(store)
        leader = identity("leader")
        scout_a = identity("scout-a")
        scout_b = identity("scout-b")
        reviewer_a = identity("reviewer-a")
        reviewer_b = identity("reviewer-b")
        sybil = identity("sybil-reviewer", parent="reviewer-a")
        identities = {
            item.instance_id: item
            for item in (leader, scout_a, scout_b, reviewer_a, reviewer_b, sybil)
        }
        for item in identities.values():
            collective.record_identity(item)

        first = FieldProgram(
            program_id="scout-program",
            version=1,
            roles=("source",),
            steps=(PrimitiveStep(operation="identity", output="result", inputs=("source",)),),
            outputs=("result",),
            support_event_ids=(digest("campaign-derivation"),),
        )
        second = FieldProgram(
            program_id="critic-program",
            version=1,
            roles=("result",),
            steps=(PrimitiveStep(operation="identity", output="final", inputs=("result",)),),
            outputs=("final",),
        )
        composed = compose_field_programs((first, second), program_id="composed-program")
        profile = digest("shared-field-profile")
        capsules = (
            make_capsule(instance_id="scout-a", field_profile=profile, program=composed, branch="low-noise"),
            make_capsule(instance_id="scout-b", field_profile=profile, program=composed, branch="high-noise"),
        )

        # Branches remain explicit and contradictory rather than being averaged.
        low = collective.graph.register(
            candidate_id="candidate-low-noise",
            branch_id="low-noise",
            domain="reasoning",
        )
        high = collective.graph.register(
            candidate_id="candidate-high-noise",
            branch_id="high-noise",
            domain="reasoning",
            parent_hypothesis_id=low.hypothesis_id,
        )
        collective.graph.link(HypothesisEdge(low.hypothesis_id, high.hypothesis_id, "contradicts"))
        collective.graph.resolve(high.hypothesis_id, "conditional")

        # Specialist routing, offer/query matching, and diversity coverage.
        collective.roles.assign(RoleAssignment("scout-a", "scout", ("field",), load=0.3))
        collective.roles.assign(RoleAssignment("reviewer-a", "critic", ("python", "evidence"), load=0.2))
        collective.roles.assign(RoleAssignment("reviewer-b", "replicator", ("python", "evidence"), load=0.1))
        collective.publish_offer(
            HiveOffer(
                offer_id="offer-replicator",
                provider_instance_id="reviewer-b",
                candidate_id="candidate-low-noise",
                kind="field-program",
                domain="reasoning",
                branch_id="low-noise",
                reliability=0.95,
                work_units=4,
                roles=("replicator",),
                diversity_keys=("python", "evidence"),
            )
        )
        query = HiveQuery(
            query_id="query-replicator",
            requester_instance_id="leader",
            kinds=("field-program",),
            domains=("reasoning",),
            desired_roles=("replicator",),
            minimum_reliability=0.8,
        )
        collective.record_query(query)
        matched_offers = collective.router.match(query)
        selected = DiversitySelector.select(
            capsules,
            {
                capsule.object_id: DiversityProfile(
                    instance_id=capsule.origin.instance_id,
                    field_profile_sha256=capsule.origin.field_profile_sha256,
                    domain="reasoning",
                    branch_id=capsule.episode.context["branch"],
                )
                for capsule in capsules
            },
            limit=2,
        )

        # Collect the complete compatible group; diversity selection is reported
        promotion = PromotionLoop(
            store,
            leader_instance_id=leader.instance_id,
            minimum_support_reviews=2,
            collective=collective,
            reviewer_profiles={
                reviewer_a.instance_id: ReviewerProfile.virgin(
                    reviewer_a.instance_id, reviewer_a.attestation_key_sha256
                ),
                reviewer_b.instance_id: ReviewerProfile.virgin(
                    reviewer_b.instance_id, reviewer_b.attestation_key_sha256
                ),
                sybil.instance_id: ReviewerProfile.virgin(
                    sybil.instance_id, sybil.attestation_key_sha256
                ),
            },
            reviewer_identities=identities,
            minimum_support_weight=0.9,
            minimum_independent_reviewers=2,
        )
        promotion.coordinator.collect_many(capsules)
        candidate_id = promotion.coordinator.groups()[0].candidate_id
        promotion.review(
            candidate_id,
            (
                ReviewerDecision(
                    reviewer_instance_id="reviewer-a",
                    result="supports",
                    review_type="independent-reproduction",
                ),
                ReviewerDecision(
                    reviewer_instance_id="reviewer-b",
                    result="supports",
                    review_type="adversarial-review",
                ),
                ReviewerDecision(
                    reviewer_instance_id="sybil-reviewer",
                    result="supports",
                    review_type="transfer-review",
                ),
            ),
        )
        quorum = collective.weighted_quorum(
            store.list_reviews(candidate_object_id=candidate_id),
            promotion.reviewer_profiles,
            identities,
            origin_instance_ids=tuple(capsule.origin.instance_id for capsule in capsules),
            minimum_support_weight=0.9,
            minimum_independent_reviewers=2,
        )
        promotion_report = promotion.run_once()
        if len(promotion_report.promoted_bundle_ids) != 1:
            raise RuntimeError(f"campaign promotion failed: {promotion_report.as_dict()}")
        bundle_id = promotion_report.promoted_bundle_ids[0]

        first_protocol = digest("campaign-protocol:v1")
        rollout_specs = measured_rollout_specs(
            store,
            root,
            bundle_id=bundle_id,
            protocol_sha256=first_protocol,
            posts=(0.8, 0.75, 0.9),
            observed_offset=10,
        )
        round_runner = MultiRoundPopulationRollout(
            store,
            hive_id="campaign-hive",
            branch="main",
            reviewer_profiles=promotion.reviewer_profiles,
        )
        first_round = round_runner.run_round(
            PopulationRoundSpec(
                bundle_id=bundle_id,
                protocol_sha256=first_protocol,
                members=rollout_specs,
                reviewer_predictions={"reviewer-a": 0.9, "reviewer-b": 0.9},
                independent_reviewer_ids=("reviewer-a", "reviewer-b"),
            )
        )
        if first_round.status != "accepted":
            raise RuntimeError(f"first population rollout failed: {first_round.as_dict()}")
        promotion.refresh_reviewer_profiles()
        next_composed = compose_field_programs(
            (first, second),
            program_id="composed-program-v2",
        )
        next_capsules = (
            make_capsule(
                instance_id="scout-a",
                field_profile=profile,
                program=next_composed,
                branch="low-noise",
            ),
            make_capsule(
                instance_id="scout-b",
                field_profile=profile,
                program=next_composed,
                branch="high-noise",
            ),
        )
        promotion.coordinator.collect_many(next_capsules)
        next_group = next(
            group
            for group in promotion.coordinator.groups()
            if group.capsules[0].candidate.object.get("program_id") == "composed-program-v2"
        )
        promotion.review(
            next_group.candidate_id,
            (
                ReviewerDecision(
                    reviewer_instance_id="reviewer-a",
                    result="supports",
                    review_type="independent-reproduction",
                ),
                ReviewerDecision(
                    reviewer_instance_id="reviewer-b",
                    result="supports",
                    review_type="adversarial-review",
                ),
            ),
        )
        successor_report = promotion.run_once()
        if len(successor_report.promoted_bundle_ids) != 1:
            raise RuntimeError(f"successor promotion failed: {successor_report.as_dict()}")
        successor_bundle_id = successor_report.promoted_bundle_ids[0]
        second_protocol = digest("campaign-protocol:v2")
        successor_specs = measured_rollout_specs(
            store,
            root,
            bundle_id=successor_bundle_id,
            protocol_sha256=second_protocol,
            posts=(0.9, 0.8, 0.95),
            observed_offset=20,
            prior=rollout_specs,
        )
        second_round = round_runner.run_round(
            PopulationRoundSpec(
                bundle_id=successor_bundle_id,
                protocol_sha256=second_protocol,
                members=successor_specs,
                reviewer_predictions={"reviewer-a": 0.95, "reviewer-b": 0.95},
                independent_reviewer_ids=("reviewer-a", "reviewer-b"),
            )
        )
        rounds = round_runner.finalize(created_ns=30)
        if rounds.status != "accepted" or second_round.status != "accepted":
            raise RuntimeError(f"population rounds failed: {rounds.as_dict()}")
        final_population = store.get_document(second_round.population_ledger_id)["content"]
        adopted_program_ids = tuple(
            sorted(
                {
                    program_id
                    for member in final_population["members"]
                    for program_id in member["adopted_program_ids"]
                }
            )
        )
        fork = collective.adaptations.propose(
            parent_bundle_id=successor_bundle_id,
            instance_id="member-1",
            parent_profile_sha256=rollout_specs[0].field_profile_sha256,
            local_profile_sha256=digest("member-1-local-profile"),
            changes={"branch": "high-noise", "temperature": 0.2},
        )
        memories = collective.consolidate(capsules, valid_for_ns=10_000)
        bridge = SemanticEventBridge()
        event = bridge.emit_population(
            source_instance_id="population-rollout",
            bundle_id=successor_bundle_id,
            ledger=rounds.as_dict(),
            causality_ids=tuple(
                outcome_id
                for record in rounds.rounds
                for outcome_id in record.outcome_ids
            ),
        )
        audit = store.audit()
        return {
            "schema": "cassifi.hive.adversarial-campaign.v1",
            "identity": {
                "attested": all(item.verify((item.instance_id + "-campaign-secret").encode("utf-8")) for item in identities.values()),
                "reviewer_count": len(identities),
            },
            "hypothesis": {
                "active_count": len(collective.graph.active(domain="reasoning")),
                "contradiction_count": len(collective.graph.contradictions(low.hypothesis_id)),
                "conditional_branch": collective.graph.nodes[high.hypothesis_id].status,
            },
            "routing": {
                "matched_offer_ids": [offer.offer_id for offer in matched_offers],
                "selected_capsule_ids": [capsule.object_id for capsule in selected],
                "specialist": collective.roles.choose("replicator").instance_id,
            },
            "composition": {
                "program_id": composed.program_id,
                "step_count": len(composed.steps),
                "prefix_code_bits": composed.prefix_code_bits,
            },
            "promotion": {
                "candidate_id": candidate_id,
                "bundle_id": bundle_id,
                "report": promotion_report.as_dict(),
                "weighted_quorum": quorum.as_dict(),
                "rejected_sybil": "sybil-reviewer" in quorum.rejected_reviewer_ids,
                "successor_bundle_id": successor_bundle_id,
                "successor_report": successor_report.as_dict(),
            },
            "live_adoption": {
                "ledger_id": second_round.population_ledger_id,
                "member_count": final_population["member_count"],
                "adopted_count": final_population["adopted_count"],
                "adopted_program_ids": list(adopted_program_ids),
                "members": list(final_population["members"]),
            },
            "population_outcome": {
                "ledger_id": second_round.population_ledger_id,
                "round_ledger_id": rounds.object_id,
                "round_count": rounds.round_count,
                "status": final_population["status"],
                "success": final_population["status"] == "accepted",
                "score": final_population["population_score"],
                "coverage": final_population["outcome_coverage"],
                "calibrated_reviewers": list(second_round.calibrated_reviewer_ids),
            },
            "population_rounds": {
                "object_id": rounds.object_id,
                **rounds.as_dict(),
            },
            "adaptation": {"fork_id": fork.fork_id, "status": fork.status},
            "memory": {
                "consolidated_count": len(memories),
                "source_count": memories[0].source_count if memories else 0,
            },
            "bridge": {
                "event_id": event.event_id,
                "cassicore_payload_sha256": sha256_value(event.cassicore_payload()),
                "cosmos_payload_sha256": sha256_value(event.cosmos_payload()),
            },
            "audit": audit,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hive-home", type=Path, help="persistent campaign store directory")
    parser.add_argument("--output", type=Path, help="write the JSON receipt to this path")
    arguments = parser.parse_args(argv)
    if arguments.hive_home is not None:
        report = run_campaign(arguments.hive_home)
    else:
        with TemporaryDirectory() as temporary:
            report = run_campaign(Path(temporary) / "hive")
    encoded = json.dumps(report, indent=2, sort_keys=True)
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded + "\n", encoding="utf-8")
    print(encoded)
    return 0


if __name__ == "__main__":
    sys.exit(main())
