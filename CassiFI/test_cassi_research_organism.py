from __future__ import annotations

from pathlib import Path
import json

import threading
import pytest

from cassi_field_owner import FieldIntelligenceOwner
from cassi_hive_collective import (
    AffectReport,
    CollaborationAssignment,
    CollaborationRequest,
    CollaborationResponse,
    CollectiveSynthesis,
    ExecutableMethod,
    MethodCompositionSpec,
    MethodConnection,
    MethodInterface,
    MethodOutputBinding,
    MethodPort,
    RepresentationTranslation,
)
from cassi_field_atlas import (
    FieldProgram,
    PrimitiveStep,
    sha256_value,
)
from cassi_research_organism import EffectJournal, OrganismError, ResearchOrganism
from cassi_research_worlds import INSTRUMENT_KIND, execute_work


def _instrument(
    artifact_home: Path,
    *,
    operation_id: str,
    strategy: str,
    context_available: bool = True,
) -> dict[str, object]:
    return execute_work(
        {
            "kind": INSTRUMENT_KIND,
            "operation_id": operation_id,
            "scenario": {
                "steps": 32,
                "change_at": 16,
                "delay": 3,
                "low": 0.0,
                "high": 1.0,
                "context_available": context_available,
                "tolerance": 0.0,
            },
            "program": {"strategy": strategy, "window": 1},
        },
        workspace=Path.cwd(),
        artifact_home=artifact_home,
    )


def test_instrument_world_exposes_a_learnable_delayed_distinction(tmp_path: Path) -> None:
    incumbent = _instrument(
        tmp_path,
        operation_id="instrument-incumbent",
        strategy="hold-last",
    )
    constructed = _instrument(
        tmp_path,
        operation_id="instrument-constructed",
        strategy="context-gated",
    )

    incumbent_evidence = incumbent["evidence"]
    constructed_evidence = constructed["evidence"]
    assert isinstance(incumbent_evidence, dict)
    assert isinstance(constructed_evidence, dict)
    assert constructed_evidence["metrics"]["accuracy"] == 1.0
    assert (
        constructed_evidence["metrics"]["accuracy"]
        > incumbent_evidence["metrics"]["accuracy"]
    )
    assert sha256_value(constructed_evidence["trace"]) == constructed_evidence["trace_sha256"]

    opportunity = constructed["learning_opportunities"][0]
    signature = opportunity["request"]["signature"]
    assert signature["prediction_semantics"] == "constraint-set"
    assert signature["horizon"] == 1
    assert signature["clock_boundary"] == {
        "decision_clock": "instrument-step",
        "outcome_clock": "instrument-step",
    }
    assert opportunity["request"]["examples"]
    assert opportunity["request"]["holdout"]

    unavailable_cue = _instrument(
        tmp_path,
        operation_id="instrument-negative-transfer",
        strategy="context-gated",
        context_available=False,
    )
    assert (
        unavailable_cue["evidence"]["metrics"]["accuracy"]
        < incumbent_evidence["metrics"]["accuracy"]
    )


def test_effect_journal_is_idempotent_and_rejects_identity_reuse(tmp_path: Path) -> None:
    journal = EffectJournal(tmp_path / "effects")
    first = journal.record(
        "effect:one",
        actor="root",
        request={"value": 1},
        result={"status": "observed"},
    )
    assert journal.record(
        "effect:one",
        actor="root",
        request={"value": 1},
        result={"status": "observed"},
    ) == first
    with pytest.raises(OrganismError, match="reused with different bytes"):
        journal.record(
            "effect:one",
            actor="root",
            request={"value": 2},
            result={"status": "observed"},
        )


def test_research_organism_discovers_transfers_restarts_and_contains_failures(
    tmp_path: Path,
) -> None:
    home = tmp_path / "organism"
    organism = ResearchOrganism(
        home,
        workspace=Path(__file__).resolve().parents[1],
        member_ids=("member-a",),
    )
    initialized = organism.initialize()
    initial_frontier = organism.frontier()
    assert {entry["status"] for entry in initial_frontier["entries"]} == {
        "incumbent",
        "incomplete",
    }
    assert all(
        entry["candidate_id"] != "construction:context-gated"
        for entry in initial_frontier["entries"]
    )
    source_paths = initialized["manifest"]["source_paths"]
    assert "CassiFI/cassi_field_owner.py" in source_paths
    assert "CassiFI/run_cassi_research_organism.py" in source_paths

    campaign = organism.run_population_round(0)
    assert campaign["phase"] == "complete"
    assert campaign["verdict"] == "accepted"
    assert campaign["candidate_id"] == "construction:context-gated"
    assert campaign["selection"]["method"] == "semantic.autonomous-agenda"
    assert campaign["root"]["comparison"]["delta_accuracy"] > 0.0
    assert campaign["publication"]["generation_id"] == "g0001"
    campaign_effect_count = organism.journal.count()

    member = campaign["members"][0]
    assert member["comparison"]["supported"] is True
    evaluation = member["adoption"]["evaluation"]
    assert evaluation["mode"] == "matched-checkpoint-frozen-knowledge"
    assert evaluation["parent_field_state_sha256"]
    assert evaluation["control_field_state_sha256"]
    assert evaluation["candidate_field_state_sha256"]

    frontier = organism.frontier()
    by_id = {entry["candidate_id"]: entry for entry in frontier["entries"]}
    assert by_id["construction:temporal-hole"]["status"] == "expanded"
    assert by_id["construction:context-gated"]["status"] == "accepted"
    assert by_id["construction:context-gated-v2"]["status"] == "proposed"
    assert by_id["construction:context-gated"]["novelty"] == [
        "new-composition",
        "new-learned-representation",
    ]

    reopened = ResearchOrganism(home)
    replay = reopened.run_population_round(0)
    assert replay["publication"]["generation_id"] == "g0001"
    assert replay["bundle_id"] == campaign["bundle_id"]
    assert reopened.journal.count() == campaign_effect_count

    boundaries = reopened.exercise_boundaries(0)
    assert boundaries["negative_transfer"]["status"] == "no-detected-gain"
    assert boundaries["unavailable_world"]["status"] == "support-gap"
    assert boundaries["failed_publication"] == {
        "status": "rejected",
        "reason": boundaries["failed_publication"]["reason"],
        "active_pointer_preserved": True,
        "active_generation": "g0001",
    }
    boundary_effect_count = reopened.journal.count()
    assert reopened.exercise_boundaries(0) == boundaries
    assert reopened.journal.count() == boundary_effect_count
    status = reopened.inspect()
    assert status["publication"]["generation_id"] == "g0001"


def test_laboratory_selection_replays_completed_field_choice(tmp_path: Path) -> None:
    home = tmp_path / "organism"
    organism = ResearchOrganism(
        home,
        workspace=Path(__file__).resolve().parents[1],
        member_ids=("member-a",),
    )
    organism.initialize()
    request = {
        "campaign_id": "replay-campaign",
        "laboratory_id": "operator-seed-radial",
        "objective": "choose a development-only operator",
        "candidates": [
            {
                "candidate_id": "candidate-a",
                "development_score": 0.75,
                "development_cost": 2,
                "development_evidence": {"validation_mean_nrmse": 0.25},
            },
            {
                "candidate_id": "candidate-b",
                "development_score": 0.50,
                "development_cost": 3,
                "development_evidence": {"validation_mean_nrmse": 0.50},
            },
        ],
    }

    first = organism.select_laboratory_candidate(**request)
    replay = ResearchOrganism(home).select_laboratory_candidate(**request)

    assert replay == first


def test_experiment_assimilation_requires_collective_review_and_adopts_exact_lesson(
    tmp_path: Path,
) -> None:
    home = tmp_path / "organism"
    organism = ResearchOrganism(
        home,
        workspace=Path(__file__).resolve().parents[1],
        member_ids=("member-a", "member-b"),
    )
    organism.initialize()
    lessons = [
        {
            "lesson_id": "trajectory-history-authority",
            "statement": "Aligned trajectory history carries residual authority.",
            "development_score": 1.0,
            "development_cost": 1.0,
            "development_evidence": {"conditional_reduction": 0.25},
        },
        {
            "lesson_id": "no-stable-history-authority",
            "statement": "History adds no stable authority after the present state.",
            "development_score": 0.0,
            "development_cost": 1.0,
            "development_evidence": {"conditional_reduction": 0.0},
        },
    ]
    member_result = {
        "controls_passed": True,
        "lesson_scores": {
            "trajectory-history-authority": 1.0,
            "no-stable-history-authority": 0.0,
        },
        "arm_ids": ["disjoint-arm"],
    }
    request = {
        "experiment_id": "synthetic-trajectory-experience",
        "laboratory_id": "trajectory-residual-authority",
        "objective": "learn only a lesson reproduced across independent field members",
        "root_result": {
            "controls_passed": True,
            "arm_ids": ["root-arm"],
            "conditional_reduction": 0.25,
        },
        "lessons": lessons,
        "member_results": {
            "member-a": {**member_result, "arm_ids": ["member-a-arm"]},
            "member-b": {**member_result, "arm_ids": ["member-b-arm"]},
        },
    }

    receipt = organism.assimilate_experiment(**request)

    assert receipt["status"] == "promoted"
    assert receipt["selected_lesson"]["lesson_id"] == "trajectory-history-authority"
    assert receipt["capsule_id"]
    assert receipt["bundle_id"]
    assert receipt["support_count"] == 2
    assert {row["review"]["result"] for row in receipt["reviews"]} == {"supports"}
    assert set(receipt["adoptions"]) == {"root", "member-a", "member-b"}
    with organism._open_residencies(include_members=True) as (root, members):
        residents = {"root": root, **members}
        hive_ids = {
            residency.session.identity.hive_id
            for residency in residents.values()
        }
        assert len(hive_ids) == 1
        assert {
            residency.session.status()["common_generation"]
            for residency in residents.values()
        } == {receipt["hive_generation"]}
        for residency in residents.values():
            learned = {
                program.program_id: program
                for program in residency.owner.state.programs
            }
            assert receipt["program_id"] in learned
            assert sha256_value(
                learned[receipt["program_id"]].as_dict()
            ) == receipt["program_sha256"]

    replay = ResearchOrganism(home).assimilate_experiment(**request)
    assert replay == receipt
    assert (
        ResearchOrganism(home).inspect()["collective_hive"]["status"][
            "current_generation"
        ]
        == receipt["hive_generation"]
    )
def test_attached_entity_field_resources_collaboration_and_cohort_survive_reload(
    tmp_path: Path,
) -> None:
    owner_home = tmp_path / "entity-field"
    organism_home = tmp_path / "organism"
    lock = threading.RLock()
    with FieldIntelligenceOwner(owner_home) as owner:
        organism = ResearchOrganism(
            organism_home,
            workspace=Path(__file__).resolve().parents[1],
            member_ids=("member-a",),
            root_owner=owner,
            root_lock=lock,
        )
        organism.initialize(
            profile={"program_capacity": 64, "stack_capacity": 64, "max_steps": 4096},
        )
        with organism._open_residencies(include_members=True) as (root, members):
            assert root.session.raw_owner is owner
            assert members["member-a"].session.raw_owner is not owner
            member_before = members["member-a"].owner.state.state_sha256
        allocation = organism.allocate_resources(
            "allocation-a",
            member_id="member-a",
            objective={"goal": "independent reproduction"},
            budgets={"resident_steps": 2},
        )
        assert allocation["state"] == "active"
        with organism._open_residencies(include_members=True) as (_, members):
            member_allocated = members["member-a"].owner.state.state_sha256
        assert member_allocated != member_before
        paused = organism.control_member(
            "pause-a", member_id="member-a", action="pause",
            reason="preserve continuation while reviewing",
        )
        assert paused["state"] == "paused"
        with pytest.raises(OrganismError, match="paused"):
            organism.advance_member("member-a", "allocation-a")
        organism.control_member(
            "resume-a", member_id="member-a", action="resume",
            reason="review complete",
        )
        with organism._open_residencies(include_members=True) as (_, members):
            member_scheduled = members["member-a"].owner.state.state_sha256
        execution = organism.advance_member("member-a", "allocation-a")
        assert execution["field_state_sha256_before"] == member_scheduled
        assert execution["field_state_sha256_after"] != member_before
        required_interface = MethodInterface(
            inputs=(
                MethodPort(
                    "candidate",
                    "scalar",
                    "field-program",
                    "score",
                ),
            ),
            outputs=(
                MethodPort(
                    "confidence",
                    "scalar",
                    "assessment",
                    "score",
                ),
            ),
        )
        request = CollaborationRequest(
            "request-a",
            "organism-root",
            {"goal": "reproduce"},
            ("replicator",),
            "field-program",
            "assessment",
            1,
            4,
            required_interface=required_interface,
        )
        assignment = CollaborationAssignment(
            "assignment-a",
            request.request_id,
            "member-a",
            "replicator",
            {"operation": "reproduce"},
            "allocation-a",
        )
        response_method = ExecutableMethod(
            program=FieldProgram(
                program_id="member-reproduction",
                version=2,
                roles=("candidate_value",),
                steps=(
                    PrimitiveStep(
                        operation="identity",
                        output="reproduced_value",
                        inputs=("candidate_value",),
                    ),
                ),
                outputs=("reproduced_value",),
            ),
            interface=MethodInterface(
                inputs=(
                    MethodPort(
                        "candidate",
                        "scalar",
                        "field-program",
                        "score",
                        "candidate_value",
                    ),
                ),
                outputs=(
                    MethodPort(
                        "reproduced",
                        "scalar",
                        "field-program",
                        "score",
                        "reproduced_value",
                    ),
                ),
            ),
            assumptions=({"independent_reproduction": True},),
            effects=("reproduces-candidate-score",),
            maximum_work=1,
            correction_ids=("member-correction-a",),
        )
        response = CollaborationResponse(
            "response-a",
            assignment.assignment_id,
            "member-a",
            "completed",
            "field-program",
            {"finding": "supported"},
            evidence_ids=("evidence-a",),
            method=response_method,
        )
        translation_method = ExecutableMethod(
            program=FieldProgram(
                program_id="assessment-translation",
                version=1,
                roles=("source_value",),
                steps=(
                    PrimitiveStep(
                        operation="identity",
                        output="translated_value",
                        inputs=("source_value",),
                    ),
                ),
                outputs=("translated_value",),
            ),
            interface=MethodInterface(
                inputs=(
                    MethodPort(
                        "finding",
                        "scalar",
                        "field-program",
                        "score",
                        "source_value",
                    ),
                ),
                outputs=(
                    MethodPort(
                        "confidence",
                        "scalar",
                        "assessment",
                        "score",
                        "translated_value",
                    ),
                ),
            ),
            preconditions=({"score": {"minimum": 0.0, "maximum": 1.0}},),
            effects=("translates-to-assessment",),
            maximum_work=1,
        )
        translation = RepresentationTranslation(
            "translation-a",
            response.response_id,
            "organism-root",
            "field-program",
            "assessment",
            {"finding": "supported"},
            {"confidence": "reproduced"},
            "validated",
            method=translation_method,
        )
        synthesis = CollectiveSynthesis(
            "synthesis-a",
            request.request_id,
            "organism-root",
            (response.response_id,),
            (translation.translation_id,),
            {"decision": "retain"},
            agreements=("supported",),
            composition=MethodCompositionSpec(
                program_id="collaborative-reproduction",
                component_ids=(
                    response.response_id,
                    translation.translation_id,
                ),
                connections=(
                    MethodConnection(
                        "$request",
                        "candidate",
                        response.response_id,
                        "candidate",
                    ),
                    MethodConnection(
                        response.response_id,
                        "reproduced",
                        translation.translation_id,
                        "finding",
                    ),
                ),
                outputs=(
                    MethodOutputBinding(
                        "confidence",
                        translation.translation_id,
                        "confidence",
                    ),
                ),
                maximum_work=3,
            ),
        )
        organism.request_collaboration(request)
        organism.assign_collaboration(assignment)
        organism.record_collaboration_response(response)
        organism.record_representation_translation(translation)
        organism.record_collective_synthesis(synthesis)
        gap_synthesis = CollectiveSynthesis(
            "synthesis-gap-a",
            request.request_id,
            "organism-root",
            (response.response_id,),
            (),
            {"decision": "seek missing assessment adapter"},
            composition=MethodCompositionSpec(
                program_id="incomplete-reproduction",
                component_ids=(response.response_id,),
                connections=(
                    MethodConnection(
                        "$request",
                        "candidate",
                        response.response_id,
                        "candidate",
                    ),
                ),
                outputs=(),
                maximum_work=2,
            ),
        )
        organism.record_collective_synthesis(gap_synthesis)
        waiting = organism.begin_collective_method_continuation(
            gap_synthesis.synthesis_id,
            "continuation-gap-a",
            {"candidate": 0.75},
        )
        assert waiting["status"] == "waiting"
        assert waiting["wait_reason"] == "capability-gap"
        assert waiting["capability_gap"]["ref"]["id"] == (
            "obligation:collaboration-capability-gap:synthesis-gap-a"
        )
        field_while_waiting = owner.state.state_sha256
        waiting_reloaded = ResearchOrganism(
            organism_home,
            root_owner=owner,
            root_lock=lock,
        )
        assert (
            waiting_reloaded.begin_collective_method_continuation(
                gap_synthesis.synthesis_id,
                "continuation-gap-a",
                {"candidate": 0.75},
            )
            == waiting
        )
        assert owner.state.state_sha256 == field_while_waiting
        assert (
            waiting_reloaded.resume_collective_method_continuation(
                "continuation-gap-a"
            )
            == waiting
        )
        assert owner.state.state_sha256 == field_while_waiting
        method_execution = organism.execute_collective_synthesis(
            synthesis.synthesis_id,
            "execution-a",
            {"candidate": 0.75},
        )
        assert method_execution["outputs"] == {"confidence": 0.75}
        with pytest.raises(OrganismError, match="identity was reused"):
            organism.execute_collective_synthesis(
                synthesis.synthesis_id,
                "execution-a",
                {"candidate": 0.5},
            )
        with pytest.raises(OrganismError, match="rejected its bindings"):
            organism.execute_collective_synthesis(
                synthesis.synthesis_id,
                "execution-invalid",
                {"candidate": "not-a-score"},
            )
        with pytest.raises(OrganismError, match="capability gaps"):
            organism.execute_collective_synthesis(
                gap_synthesis.synthesis_id,
                "execution-gap",
                {"candidate": 0.75},
            )
        affect_report = AffectReport(
            message_id="affect-message-a",
            sender_instance_id="member-a",
            recipient_scope="root",
            report_kind="concern",
            interpretation_status="tentative",
            requested_help={"kind": "review-assumption"},
            content={"concern": "representation may be lossy"},
            applicability={"request_id": request.request_id},
            question_ref={"owner": "member-a", "id": "question-a"},
            episode_id="member-episode-a",
            evidence_roots=({"owner": "member-a", "id": "evidence-a"},),
            visibility_refs=("evidence-a:summary",),
        )
        affect_receipt = organism.record_affect_report(affect_report)
        assert affect_receipt["receipt_ref"]["kind"] == "Event"
        assert affect_receipt["appraisal"]["appraisal"]["kind"] == "Event"
        view = organism.collaboration_view()
        assert len(view["requests"]) == 1
        assert len(view["responses"]) == 1
        assert len(view["capability_gaps"]) == 1
        assert len(view["continuations"]) == 1
        projected_wait = view["continuations"][0]
        assert projected_wait["status"] == "waiting"
        assert projected_wait["continuation_ref"] == waiting[
            "continuation_ref"
        ]
        assert projected_wait["call"] == waiting["call"]
        assert len(view["executable_syntheses"]) == 1
        assert view["resource_allocations"][0]["remaining"]["resident_steps"] == 1
        assert len(view["affect_reports"]) == 1
        with organism._open_residencies(include_members=False) as (root, _):
            report = root._record("organism:attributed-response:response-a")
            assert report is not None
            assert report["payload"]["reporter_instance_id"] == "member-a"
            program = root._record(
                "program:collaboration-translation:translation-a"
            )
            binding = root._record(
                "binding:collaboration-translation:translation-a"
            )
            synthesis_program = root._record(
                "program:collaboration-synthesis:synthesis-a"
            )
            gap = root._record(
                "obligation:collaboration-capability-gap:synthesis-gap-a"
            )
            synthesis_record = root._record("organism:synthesis:synthesis-a")
            assert all(
                item is not None
                for item in (
                    program,
                    binding,
                    synthesis_program,
                    gap,
                    synthesis_record,
                )
            )
            program_payload = organism._unwrap_program_record(
                program["payload"]
            )
            assert program_payload["program_role"] == "procedure"
            assert program_payload["collaboration_program_role"] == (
                "executable-representation-translation"
            )
            synthesis_payload = organism._unwrap_program_record(
                synthesis_program["payload"]
            )
            assert synthesis_payload["method"]["program"]["version"] == 1
            assert gap["payload"]["gaps"][0]["kind"] == (
                "missing-output-binding"
            )
            assert synthesis_record["payload"][
                "translation_binding_refs"
            ][0]["id"] == binding["id"]
        completed_gap_synthesis = CollectiveSynthesis(
            gap_synthesis.synthesis_id,
            request.request_id,
            "organism-root",
            (response.response_id,),
            (translation.translation_id,),
            {"decision": "completed assessment adapter"},
            composition=MethodCompositionSpec(
                program_id="completed-reproduction",
                component_ids=(
                    response.response_id,
                    translation.translation_id,
                ),
                connections=(
                    MethodConnection(
                        "$request",
                        "candidate",
                        response.response_id,
                        "candidate",
                    ),
                    MethodConnection(
                        response.response_id,
                        "reproduced",
                        translation.translation_id,
                        "finding",
                    ),
                ),
                outputs=(
                    MethodOutputBinding(
                        "confidence",
                        translation.translation_id,
                        "confidence",
                    ),
                ),
                maximum_work=3,
            ),
        )
        organism.record_collective_synthesis(completed_gap_synthesis)
        resolved_view = organism.collaboration_view()
        assert resolved_view["capability_gaps"] == []
        assert len(resolved_view["executable_syntheses"]) == 2
        resumed = resolved_view["continuations"][0]
        assert resumed["status"] == "completed"
        assert resumed["result"]["program_ref"]["content_version"] == 1
        assert resumed["result"]["outputs"] == {"confidence": 0.75}
        field_after_resume = owner.state.state_sha256
        assert organism.resume_collective_method_continuation(
            "continuation-gap-a"
        ) == resumed
        assert owner.state.state_sha256 == field_after_resume
        invalid = organism.begin_collective_method_continuation(
            synthesis.synthesis_id,
            "continuation-invalid-a",
            {"candidate": "not-a-score"},
        )
        assert invalid["status"] == "ready"
        resume_identity = {
            "continuation_id": "continuation-invalid-a",
            "synthesis_id": synthesis.synthesis_id,
        }
        resume_body = {
            "action_id": (
                "collective-next:resume:"
                f"{sha256_value(resume_identity)[:32]}"
            ),
            "continuation_id": "continuation-invalid-a",
            "kind": "resume-continuation",
            "synthesis_id": synthesis.synthesis_id,
        }
        resume_candidate = {
            **resume_body,
            "candidate_sha256": sha256_value(resume_body),
        }
        resumed_action = organism.advance_collective_investigation(
            operation_id="collective-next-resume-invalid-a",
            candidate=resume_candidate,
        )
        assert resumed_action["status"] == "resumed"
        assert resumed_action["effects"]["continuation"]["status"] == "blocked"
        assert (
            organism.advance_collective_investigation(
                operation_id="collective-next-resume-invalid-a",
                candidate=resume_candidate,
            )
            == resumed_action
        )
        blocked = organism.resume_collective_method_continuation(
            "continuation-invalid-a"
        )
        assert blocked["status"] == "blocked"
        failure = blocked["result"]["results"]["collective-method"]["result"]
        assert failure["accepted"] is False
        assert failure["error"] == "invalid-bindings"
        field_after_block = owner.state.state_sha256
        assert organism.resume_collective_method_continuation(
            "continuation-invalid-a"
        ) == blocked
        assert owner.state.state_sha256 == field_after_block
        with pytest.raises(OrganismError, match="immutable"):
            organism.record_collective_synthesis(
                CollectiveSynthesis(
                    synthesis.synthesis_id,
                    request.request_id,
                    "organism-root",
                    (response.response_id,),
                    (translation.translation_id,),
                    {"decision": "changed after method admission"},
                    composition=synthesis.composition,
                )
            )
        settled = organism.settle_resource_allocation(
            "allocation-a",
            "settlement-a",
            measured_consumption={"resident_steps": 1},
            status="completed",
        )
        assert settled["lease"]["state"] == "closed"
        assert organism.settle_resource_allocation(
            "allocation-a",
            "settlement-a",
            measured_consumption={"resident_steps": 1},
            status="completed",
        ) == settled
        migration = organism.migrate_cohort(
            "migration-a",
            member_ids=("member-b",),
            reason="move to a fresh independent specialist",
            profile={"program_capacity": 64, "stack_capacity": 64, "max_steps": 4096},
        )
        assert migration["transfer"] == "public-hive-artifacts-only"
        assert migration["adaptive_state_copied"] is False
        assert migration["publication_boundary"]["state"] == "quiesced-for-switch"
        assert migration["runtime"]["source_closure_sha256"]
        assert len(migration["source_closure"]) >= 5
        assert {
            row["path"] for row in migration["source_closure"]
        } == set(organism._load_manifest()["source_paths"])
        assert set(migration["owner_manifests"]) == {"root", "member-b"}
        member_manifest = migration["owner_manifests"]["member-b"]
        assert member_manifest["disposition"] == "new-independent-owner"
        assert member_manifest["predecessor_field_state_sha256"] is None
        assert member_manifest["prepared_field_state_sha256"] == (
            migration["prepared_field_state_sha256"]["member-b"]
        )
        assert member_manifest["runtime"] == migration["runtime"]
        assert member_manifest["schemas"] == migration["schemas"]
        assert member_manifest["continuation"]
        assert member_manifest["record_mapping"]
        assert member_manifest["effect_journal"]["cursor"] == 0
        assert migration["owner_manifests"]["root"]["allocations"]
        assert organism.inspect()["cohort"]["active_member_ids"] == ["member-b"]
        switched = organism._cohort()
        organism.cohort_path.write_text(
            json.dumps(
                {
                    "schema": switched["schema"],
                    "generation": migration["source_generation"],
                    "active_member_ids": migration["source_member_ids"],
                    "migration_id": None,
                },
                sort_keys=True,
                separators=(",", ":"),
            ),
            encoding="utf-8",
        )
        assert organism.recover_cohort_migration("migration-a")[
            "active_member_ids"
        ] == ["member-b"]
        owner_after = owner.state.state_sha256
        reloaded = ResearchOrganism(
            organism_home,
            root_owner=owner,
            root_lock=lock,
        )
        assert reloaded.inspect()["cohort"]["active_member_ids"] == ["member-b"]
        assert len(reloaded.collaboration_view()["syntheses"]) == 3
        assert reloaded.execute_collective_synthesis(
            "synthesis-a",
            "execution-a",
            {"candidate": 0.75},
        ) == method_execution
        assert owner.state.state_sha256 == owner_after
        stale = reloaded.begin_collective_method_continuation(
            "synthesis-a",
            "continuation-stale-a",
            {"candidate": 0.75},
        )
        assert stale["status"] == "ready"
        with reloaded._open_residencies(
            include_members=False
        ) as (root, _):
            current = root._record(
                "program:collaboration-synthesis:synthesis-a"
            )
            assert current is not None
            changed_program = reloaded._unwrap_program_record(
                current["payload"]
            )
            changed_program["mutation_control"] = "replacement"
            reloaded._write_record(
                root,
                record_id=current["id"],
                kind="Program",
                payload=changed_program,
                epistemic_kind="derived",
            )
        with pytest.raises(
            OrganismError,
            match="collective continuation method changed after suspension",
        ):
            reloaded.resume_collective_method_continuation(
                "continuation-stale-a"
            )


def test_organism_routes_a_parked_method_gap_to_hive_and_wakes_it(
    tmp_path: Path,
) -> None:
    owner_home = tmp_path / "root-field"
    organism_home = tmp_path / "organism"
    lock = threading.RLock()
    with FieldIntelligenceOwner(owner_home) as owner:
        organism = ResearchOrganism(
            organism_home,
            workspace=Path(__file__).resolve().parents[1],
            member_ids=("member-a", "member-b", "member-c"),
            root_owner=owner,
            root_lock=lock,
        )
        organism.initialize(
            profile={
                "program_capacity": 64,
                "stack_capacity": 64,
                "max_steps": 4096,
            },
        )
        required_interface = MethodInterface(
            inputs=(
                MethodPort(
                    "candidate",
                    "scalar",
                    "field-program",
                    "score",
                ),
            ),
            outputs=(
                MethodPort(
                    "confidence",
                    "scalar",
                    "assessment",
                    "score",
                ),
            ),
        )
        request = CollaborationRequest(
            "route-request-a",
            "organism-root",
            {
                "goal": (
                    "compose an assessment from independent analysis "
                    "and evidence"
                )
            },
            ("investigator",),
            "field-program",
            "assessment",
            4,
            8,
            required_interface=required_interface,
        )
        organism.request_collaboration(request)
        final_allocation = organism.allocate_resources(
            "route-final-allocation-a",
            member_id="member-a",
            objective={"goal": "retain the final assessment method"},
            budgets={"resident_steps": 1},
        )
        final_assignment = CollaborationAssignment(
            "route-final-assignment-a",
            request.request_id,
            "member-a",
            "investigator",
            {"operation": "combine analysis and evidence"},
            final_allocation["allocation_id"],
        )
        organism.assign_collaboration(final_assignment)
        final_method = ExecutableMethod(
            program=FieldProgram(
                program_id="route-final-method",
                version=1,
                roles=("analysis_value", "evidence_value"),
                steps=(
                    PrimitiveStep(
                        operation="add",
                        output="confidence_value",
                        inputs=("analysis_value", "evidence_value"),
                    ),
                ),
                outputs=("confidence_value",),
            ),
            interface=MethodInterface(
                inputs=(
                    MethodPort(
                        "analysis",
                        "scalar",
                        "analysis",
                        "score",
                        "analysis_value",
                    ),
                    MethodPort(
                        "evidence",
                        "scalar",
                        "evidence",
                        "score",
                        "evidence_value",
                    ),
                ),
                outputs=(
                    MethodPort(
                        "confidence",
                        "scalar",
                        "assessment",
                        "score",
                        "confidence_value",
                    ),
                ),
            ),
            maximum_work=1,
        )
        final_response = CollaborationResponse(
            "route-final-response-a",
            final_assignment.assignment_id,
            "member-a",
            "completed",
            "assessment",
            {
                "finding": (
                    "a final assessment method awaits analysis and evidence"
                )
            },
            method=final_method,
        )
        organism.record_collaboration_response(final_response)
        incomplete = CollectiveSynthesis(
            "route-synthesis-a",
            request.request_id,
            "organism-root",
            (final_response.response_id,),
            (),
            {"decision": "assemble a staged investigation"},
            composition=MethodCompositionSpec(
                program_id="route-investigation-method",
                component_ids=(final_response.response_id,),
                connections=(),
                outputs=(
                    MethodOutputBinding(
                        "confidence",
                        final_response.response_id,
                        "confidence",
                    ),
                ),
                maximum_work=4,
            ),
        )
        organism.record_collective_synthesis(incomplete)
        waiting = organism.begin_collective_method_continuation(
            incomplete.synthesis_id,
            "route-continuation-a",
            {"candidate": 0.25},
        )
        assert waiting["status"] == "waiting"
        parked = organism.collaboration_view()["capability_dispatches"]
        assert len(parked) == 2
        assert {item["state"] for item in parked} == {"parked"}
        first_gap = organism.collaboration_view()["capability_gaps"][0][
            "gaps"
        ][0]
        route_body = {
            "action_id": "collective-next:route-a",
            "gap_sha256": sha256_value(first_gap),
            "kind": "route-capability-gap",
            "port": first_gap["port"],
            "synthesis_id": incomplete.synthesis_id,
        }
        route_candidate = {
            **route_body,
            "candidate_sha256": sha256_value(route_body),
        }
        routed = organism.advance_collective_investigation(
            operation_id="collective-action-route-a",
            candidate=route_candidate,
        )
        assert routed["status"] == "waiting"
        assert routed["reason"] == "no-schedulable-member"
        assert len(routed["effects"]["dispatches"]) == 1
        assert routed["effects"]["dispatches"][0]["state"] == "parked"
        assert (
            organism.advance_collective_investigation(
                operation_id="collective-action-route-a",
                candidate=route_candidate,
            )
            == routed
        )
        recorded_actions = organism.collaboration_view()["collective_actions"]
        assert len(recorded_actions) == 1
        assert recorded_actions[0]["candidate"] == route_candidate
        assert recorded_actions[0]["status"] == "waiting"
        analysis_method = ExecutableMethod(
            program=FieldProgram(
                program_id="route-analysis-method",
                version=1,
                roles=("candidate_value",),
                steps=(
                    PrimitiveStep(
                        operation="identity",
                        output="analysis_intermediate",
                        inputs=("candidate_value",),
                    ),
                    PrimitiveStep(
                        operation="identity",
                        output="analysis_value",
                        inputs=("analysis_intermediate",),
                    ),
                ),
                outputs=("analysis_value",),
            ),
            interface=MethodInterface(
                inputs=(
                    MethodPort(
                        "candidate",
                        "scalar",
                        "field-program",
                        "score",
                        "candidate_value",
                    ),
                ),
                outputs=(
                    MethodPort(
                        "analysis",
                        "scalar",
                        "analysis",
                        "score",
                        "analysis_value",
                    ),
                ),
            ),
            maximum_work=2,
        )
        evidence_method = ExecutableMethod(
            program=FieldProgram(
                program_id="route-evidence-method",
                version=1,
                roles=("candidate_value",),
                steps=(
                    PrimitiveStep(
                        operation="identity",
                        output="evidence_value",
                        inputs=("candidate_value",),
                    ),
                ),
                outputs=("evidence_value",),
            ),
            interface=MethodInterface(
                inputs=(
                    MethodPort(
                        "candidate",
                        "scalar",
                        "field-program",
                        "score",
                        "candidate_value",
                    ),
                ),
                outputs=(
                    MethodPort(
                        "evidence",
                        "scalar",
                        "evidence",
                        "score",
                        "evidence_value",
                    ),
                ),
            ),
            maximum_work=1,
        )
        analysis_capability = organism.register_member_capability(
            "analysis-stage-a",
            member_id="member-b",
            roles=("investigator",),
            kind="procedure",
            domain="analysis",
            reliability=0.95,
            work_units=1,
            method=analysis_method,
        )
        evidence_capability = organism.register_member_capability(
            "evidence-stage-a",
            member_id="member-c",
            roles=("investigator",),
            kind="procedure",
            domain="evidence",
            reliability=0.9,
            work_units=1,
            method=evidence_method,
        )
        assert analysis_capability["method_sha256"]
        assert evidence_capability["method_sha256"]
        dispatched = organism.collaboration_view()["capability_dispatches"]
        by_representation = {
            item["gap"]["expected"]["representation"]: item
            for item in dispatched
        }
        assert by_representation["analysis"]["state"] == "assigned"
        assert by_representation["evidence"]["state"] == "assigned"
        assert {
            item["member_obligation_ref"]["kind"]
            for item in by_representation.values()
        } == {"Obligation"}
        organism.advance_resident()
        resolved = organism.collaboration_view()
        final_dispatches = {
            item["gap"]["expected"]["representation"]: item
            for item in resolved["capability_dispatches"]
        }
        assert {item["state"] for item in final_dispatches.values()} == {
            "admitted"
        }
        assert {
            item["agenda"]["state"] for item in final_dispatches.values()
        } == {"responded"}
        assert resolved["capability_gaps"] == []
        assert resolved["translations"] == []
        investigation = resolved["investigations"][0]
        assert investigation["state"] == "ready"
        assert investigation["component_count"] == 3
        assert investigation["contributed_stage_count"] == 2
        assert investigation["stage_count"] == 3
        assert any(
            stage["state"] == "assembling"
            and stage["component_count"] == 2
            for stage in investigation["stages"]
        )
        assert {
            stage["dispatch"]["member_id"]
            for stage in investigation["stages"]
            if stage["dispatch"] is not None
        } == {"member-b", "member-c"}
        automatic_responses = [
            item["content"]
            for item in resolved["responses"]
            if item["content"]["response_id"].startswith(
                "capability-response:"
            )
        ]
        assert {
            item["responder_instance_id"] for item in automatic_responses
        } == {"member-b", "member-c"}
        assert len(automatic_responses) == 2
        assert {
            item["content"]["method_sha256"]
            for item in automatic_responses
        } == {
            analysis_capability["method_sha256"],
            evidence_capability["method_sha256"],
        }
        for representation in ("analysis", "evidence"):
            allocation = next(
                item
                for item in resolved["resource_allocations"]
                if item["allocation_id"]
                == final_dispatches[representation]["resource_allocation_id"]
            )
            assert allocation["consumed"]["resident_steps"] == 1
            assert allocation["remaining"]["resident_steps"] == 0
            assert allocation["state"] == "exhausted"
        with organism._open_residencies(include_members=True) as (
            _root,
            members,
        ):
            for representation, member_id in (
                ("analysis", "member-b"),
                ("evidence", "member-c"),
            ):
                dispatch = final_dispatches[representation]
                obligation = members[member_id]._record(
                    dispatch["member_obligation_ref"]["id"]
                )
                assert obligation is not None
                assert obligation["payload"]["state"] == "fulfilled"
                assert members[member_id]._record(
                    dispatch["agenda"]["event"]["id"]
                ) is not None
        continuation = resolved["continuations"][0]
        assert continuation["status"] == "completed"
        assert continuation["result"]["outputs"] == {"confidence": 0.5}
        reloaded = ResearchOrganism(
            organism_home,
            root_owner=owner,
            root_lock=lock,
        )
        maintenance = reloaded.maintain_collective_capability_gaps()
        assert maintenance["admitted"] == []
        reloaded.advance_resident()
        replayed = reloaded.collaboration_view()
        assert replayed["investigations"][0]["state"] == "ready"
        assert replayed["continuations"][0]["result"] == continuation["result"]
        assert sum(
            1
            for item in replayed["responses"]
            if item["content"]["response_id"].startswith(
                "capability-response:"
            )
        ) == 2


def test_organism_develops_a_parked_capability_and_learns_provider_outcome(
    tmp_path: Path,
) -> None:
    owner_home = tmp_path / "root-field"
    organism_home = tmp_path / "organism"
    lock = threading.RLock()
    with FieldIntelligenceOwner(owner_home) as owner:
        organism = ResearchOrganism(
            organism_home,
            workspace=Path(__file__).resolve().parents[1],
            member_ids=("member-a", "member-b"),
            root_owner=owner,
            root_lock=lock,
        )
        organism.initialize(
            profile={
                "program_capacity": 64,
                "stack_capacity": 64,
                "max_steps": 4096,
            },
        )

        def seed_gap(
            prefix: str,
            *,
            target_representation: str,
            output_name: str,
            value: float,
        ) -> tuple[str, str]:
            request = CollaborationRequest(
                f"develop-request-{prefix}",
                "organism-root",
                {"goal": f"construct the missing {output_name} method"},
                ("investigator",),
                "field-program",
                target_representation,
                2,
                4,
                required_interface=MethodInterface(
                    inputs=(
                        MethodPort(
                            "candidate",
                            "scalar",
                            "field-program",
                            "score",
                        ),
                    ),
                    outputs=(
                        MethodPort(
                            output_name,
                            "scalar",
                            target_representation,
                            "score",
                        ),
                    ),
                ),
            )
            organism.request_collaboration(request)
            allocation = organism.allocate_resources(
                f"develop-allocation-{prefix}",
                member_id="member-a",
                objective={"goal": "supply an initial analysis component"},
                budgets={"resident_steps": 1},
            )
            assignment = CollaborationAssignment(
                f"develop-assignment-{prefix}",
                request.request_id,
                "member-a",
                "investigator",
                {"operation": "preserve the input as analysis"},
                allocation["allocation_id"],
            )
            organism.assign_collaboration(assignment)
            analysis_representation = f"analysis-{prefix}"
            method = ExecutableMethod(
                program=FieldProgram(
                    program_id=f"develop-analysis-{prefix}",
                    version=1,
                    roles=("candidate_value",),
                    steps=(
                        PrimitiveStep(
                            operation="identity",
                            output="analysis_value",
                            inputs=("candidate_value",),
                        ),
                    ),
                    outputs=("analysis_value",),
                ),
                interface=MethodInterface(
                    inputs=(
                        MethodPort(
                            "candidate",
                            "scalar",
                            "field-program",
                            "score",
                            "candidate_value",
                        ),
                    ),
                    outputs=(
                        MethodPort(
                            "analysis",
                            "scalar",
                            analysis_representation,
                            "score",
                            "analysis_value",
                        ),
                    ),
                ),
                maximum_work=1,
            )
            response = CollaborationResponse(
                f"develop-response-{prefix}",
                assignment.assignment_id,
                "member-a",
                "completed",
                analysis_representation,
                {"finding": "the final typed output remains missing"},
                method=method,
            )
            organism.record_collaboration_response(response)
            synthesis = CollectiveSynthesis(
                f"develop-synthesis-{prefix}",
                request.request_id,
                "organism-root",
                (response.response_id,),
                (),
                {"decision": "develop the missing final capability"},
                composition=MethodCompositionSpec(
                    program_id=f"develop-composition-{prefix}",
                    component_ids=(response.response_id,),
                    connections=(
                        MethodConnection(
                            "$request",
                            "candidate",
                            response.response_id,
                            "candidate",
                        ),
                    ),
                    outputs=(),
                    maximum_work=4,
                ),
            )
            organism.record_collective_synthesis(synthesis)
            continuation_id = f"develop-continuation-{prefix}"
            continuation = organism.begin_collective_method_continuation(
                synthesis.synthesis_id,
                continuation_id,
                {"candidate": value},
            )
            assert continuation["status"] == "waiting"
            return synthesis.synthesis_id, continuation_id

        first_synthesis, first_continuation = seed_gap(
            "first",
            target_representation="assessment",
            output_name="confidence",
            value=0.25,
        )
        seed_gap(
            "second",
            target_representation="verdict",
            output_name="decision",
            value=0.75,
        )
        before = organism.collaboration_view()
        opportunity = next(
            row
            for row in before["capability_development_opportunities"]
            if row["synthesis_id"] == first_synthesis
            and row["member_id"] == "member-b"
        )
        source = next(
            row
            for row in opportunity["sources"]
            if row["port"]["representation"] == "field-program"
        )
        candidate_body = {
            "action_id": "collective-next:develop:first",
            "dispatch_id": opportunity["dispatch_id"],
            "expected": opportunity["expected"],
            "gap_sha256": opportunity["gap_sha256"],
            "kind": "develop-capability-gap",
            "maximum_work": opportunity["maximum_work"],
            "member_id": opportunity["member_id"],
            "opportunity_sha256": opportunity["opportunity_sha256"],
            "port": opportunity["expected"]["name"],
            "provider_outcomes": opportunity["provider_outcomes"],
            "request_context": {
                "request_id": opportunity["request_id"],
                "objective": {
                    "goal": "construct the missing confidence method",
                },
            },
            "role": opportunity["role"],
            "sources": opportunity["sources"],
            "synthesis_id": opportunity["synthesis_id"],
        }
        candidate = {
            **candidate_body,
            "candidate_sha256": sha256_value(candidate_body),
        }
        development = {
            "schema": "cassi.entity.collective-capability-development.v1",
            "summary": (
                "Preserve the bounded candidate score as the requested "
                "confidence value."
            ),
            "source_ids": [source["source_id"]],
            "steps": [
                {
                    "operation": "identity",
                    "output": "confidence",
                    "inputs": [source["symbol"]],
                    "literal": None,
                }
            ],
            "assumptions": [
                "The candidate score is already calibrated on the requested scale."
            ],
            "preconditions": [
                "The candidate is a finite scalar score."
            ],
            "effects": ["Produces one assessment-valued confidence score."],
            "uncertainty": 0.25,
        }
        receipt = organism.advance_collective_investigation(
            operation_id="collective-action-develop-first",
            candidate=candidate,
            development=development,
        )
        assert receipt["status"] == "recovered"
        assert receipt["reason"] == (
            "developed-method-executed-and-continuation-completed"
        )
        assert receipt["effects"]["dispatch"]["state"] == "admitted"
        assert receipt["effects"]["advancement"][0]["state"] == "responded"
        assert receipt["effects"]["method_sha256"]
        assert organism.advance_collective_investigation(
            operation_id="collective-action-develop-first",
            candidate=candidate,
            development=development,
        ) == receipt
        with pytest.raises(
            OrganismError,
            match="operation identity was reused",
        ):
            organism.advance_collective_investigation(
                operation_id="collective-action-develop-first",
                candidate=candidate,
                development={**development, "uncertainty": 0.5},
            )

        after = organism.collaboration_view()
        first = next(
            row
            for row in after["continuations"]
            if row["continuation_id"] == first_continuation
        )
        assert first["status"] == "completed"
        assert first["result"]["outputs"] == {"confidence": 0.25}
        capability = receipt["effects"]["capability"]
        with organism._open_residencies(include_members=True) as (
            _root,
            members,
        ):
            method_record = members["member-b"]._record(
                capability["method_ref"]["id"]
            )
            assert method_record is not None
            assert method_record["kind"] == "Program"
            obligation = members["member-b"]._record(
                receipt["effects"]["dispatch"]["member_obligation_ref"]["id"]
            )
            assert obligation is not None
            assert obligation["payload"]["state"] == "fulfilled"
        learned = next(
            row
            for row in after["capability_development_opportunities"]
            if row["synthesis_id"] == "develop-synthesis-second"
            and row["member_id"] == "member-b"
        )
        assert learned["provider_outcomes"] == {
            "attempts": 1,
            "failed": 0,
            "pending": 0,
            "succeeded": 1,
            "reliability": pytest.approx(2 / 3),
        }
        reloaded = ResearchOrganism(
            organism_home,
            root_owner=owner,
            root_lock=lock,
        )
        reopened = reloaded.collaboration_view()
        reopened_first = next(
            row
            for row in reopened["continuations"]
            if row["continuation_id"] == first_continuation
        )
        assert reopened_first["result"] == first["result"]
