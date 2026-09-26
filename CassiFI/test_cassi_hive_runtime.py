from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory


from cassi_field_atlas import FieldProgram, PrimitiveStep, sha256_value
from cassi_field_hive import ExperienceCandidate, ExperienceEvidence, Review
from cassi_field_owner import FieldIntelligenceOwner
from cassi_hive_coordinator import HiveCoordinator
from cassi_hive_promotion import PromotionLoop, ReviewerDecision
from cassi_hive_runtime import HiveField
from cassi_hive_store import DEFAULT_HIVE_HOME, EXPERIENCE_SCHEMA, LocalHiveStore, decode_capsule, make_document
from cassi_hive_collective import ExecutionAssessment, OutcomeMetric


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def shared_program(program_id: str = "hive-program") -> FieldProgram:
    return FieldProgram(
        program_id=program_id,
        version=1,
        roles=("source",),
        steps=(PrimitiveStep(operation="identity", output="result", inputs=("source",)),),
        outputs=("result",),
    )




def evidence_for(label: str) -> ExperienceEvidence:
    return ExperienceEvidence(
        support_event_ids=(digest(f"{label}:support"),),
        assessment_ids=(digest(f"{label}:assessment"),),
        held_out_results=({"loss": 0.0, "label": label},),
        counterexamples=(),
        derivation_roots=(),
    )


def test_policy_and_store_round_trip() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            document = make_document("test.document.v1", {"value": 3})
            object_id = store.put_document(document)
            assert store.get_document(object_id) == document
            assert store.current_generation == 0
        with HiveField.open(root / "field", hive_home=root / "hive", mode="isolated") as field:
            assert field.skills.export_enabled
            field.skills.disable_export()
            assert not field.skills.export_enabled
            field.skills.enable_export()
            assert field.skills.export_enabled



def test_owner_facade_automatically_exports_transition() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with HiveField.open(root / "field", hive_home=root / "hive", mode="isolated") as field:
            receipt = field.owner.configure_program("auto:configure", shared_program("auto-program"))
            assert receipt.operation_id == "auto:configure"
            documents = field.hive.list_documents(schema=EXPERIENCE_SCHEMA)
            assert len(documents) == 1
            capsule = decode_capsule(documents[0])
            assert capsule.candidate.kind == "field-program"
            assert capsule.candidate.object["portable_transfer"] is True

def _publish_capsule(
    root: Path,
    *,
    instance_id: str,
    program_id: str,
    portable: bool = True,
) -> str:
    with HiveField.open(
        root / instance_id,
        hive_home=root / "hive",
        hive_id="main",
        instance_id=instance_id,
        mode="scout",
        metadata={"test_name": "hive-runtime", "arm": "scout"},
    ) as field:
        program = shared_program(program_id)
        if portable:
            field.owner.configure_program(f"{instance_id}:configure", program)
        else:
            receipt = field.raw_owner.configure_program(f"{instance_id}:configure", program)
            field.publish_experience(
                transition=receipt.as_dict(),
                task_id="publish-procedure",
                context={"domain": "test"},
                action={"operation": "configure-program"},
                prediction={"program_id": program_id},
                outcome={"program_id": program_id, "status": "configured"},
                candidate=ExperienceCandidate(
                    kind="procedure",
                    object={"program_id": program_id},
                    operation_plan=(
                        {
                            "arguments": {"program_id": program_id},
                            "method": "configure_program",
                            "operation": "owner-transition",
                        },
                    ),
                    guards=(),
                    dependencies=(),
                ),
                evidence=evidence_for(instance_id),
            )
        documents = field.hive.list_documents(schema=EXPERIENCE_SCHEMA)
        assert len(documents) == 1
        capsule = decode_capsule(documents[0])
        if portable:
            assert capsule.candidate.kind == "field-program"
            assert capsule.candidate.object["portable_transfer"] is True
        else:
            assert capsule.candidate.kind == "procedure"
        return capsule.object_id


def test_three_stage_scout_review_member_flow() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        capsule_id = _publish_capsule(root, instance_id="scout-a", program_id="shared-program")
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            groups = coordinator.groups()
            assert len(groups) == 1
            group = groups[0]
            assert group.capsules[0].object_id == capsule_id
            coordinator.review(
                Review(
                    reviewer_instance_id="reviewer-a",
                    review_type="independent-reproduction",
                    result="supports",
                    evidence_ids=(digest("review-a"),),
                ),
                candidate_id=group.candidate_id,
            )
            coordinator.review(
                Review(
                    reviewer_instance_id="reviewer-b",
                    review_type="adversarial-review",
                    result="supports",
                    evidence_ids=(digest("review-b"),),
                ),
                candidate_id=group.candidate_id,
            )
            bundle = coordinator.promote(candidate_id=group.candidate_id)
            assert bundle.predecessor_common_generation == 0
            assert store.current_generation == 1

        with HiveField.open(
            root / "member",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="member-a",
            mode="member",
        ) as member:
            assert member.status()["common_generation"] == 1
            assert member.status()["adopted_bundle_ids"] == [bundle.object_id]
            learned = next(row for row in member.owner.state.programs if row.program_id == "shared-program")
            assert learned.status == "candidate"
            assert member.timeline()[0]["bundle_id"] == bundle.object_id

def test_member_adoption_binds_receipt_to_outcome_evidence() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _publish_capsule(root, instance_id="scout-a", program_id="outcome-program")
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = coordinator.groups()[0]
            for reviewer in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(reviewer),),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle = coordinator.promote(candidate_id=group.candidate_id)
            with HiveField.open(
                root / "member",
                hive=store,
                hive_id="main",
                instance_id="member-outcome",
                mode="member",
                sync_mode="manual",
            ) as member:
                adopted = member.adopt(bundle_ids=(bundle.object_id,))
                assert adopted.applied == (bundle.object_id,)
                receipt_id = member.status()["adoption_receipt_ids"][0]
                trace_id = store.put_document(
                    make_document(
                        "cassifi.hive.execution-trace.v1",
                        {"rows": [{"expected": 1, "observed": 1}]},
                    )
                )
                assessment = ExecutionAssessment(
                    bundle_id=bundle.object_id,
                    recipient_instance_id="member-outcome",
                    adoption_receipt_id=receipt_id,
                    protocol_sha256=digest("outcome-protocol"),
                    evaluator_id="test-fixed-evaluator",
                    evaluator_version="1",
                    trace_document_ids=(trace_id,),
                    metrics=(
                        OutcomeMetric(
                            "held_out_accuracy",
                            0.5,
                            0.5,
                            0.8,
                        ),
                    ),
                    held_out=True,
                    scoring_rule="fixed-trace-accuracy-v1",
                    observed_ns=10,
                )
                member.collective.record_execution_assessment(assessment)
                report, outcome = member.adopt_and_record_outcome(
                    bundle.object_id,
                    assessment_id=assessment.object_id,
                )
                assert report.applied == (bundle.object_id,)
                assert outcome.adoption_receipt_id
                assert outcome.success
                assert store.has_object(outcome.object_id)
                assert member.status()["adoption_receipt_ids"] == [
                    outcome.adoption_receipt_id
                ]


def test_manual_import_stages_then_adopts_and_replays() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _publish_capsule(root, instance_id="scout-a", program_id="manual-program")
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = coordinator.groups()[0]
            for reviewer in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(reviewer),),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle = coordinator.promote(candidate_id=group.candidate_id)

        with HiveField.open(
            root / "member",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="member-a",
            mode="member",
            apply_mode="manual",
            sync_mode="manual",
        ) as member:
            staged = member.sync()
            assert staged.staged == (bundle.object_id,)
            assert member.status()["common_generation"] == 0
            applied = member.adopt()
            assert applied.applied == (bundle.object_id,)
            assert member.status()["common_generation"] == 1
            replay = member.adopt(bundle_ids=(bundle.object_id,))
            assert replay.replayed == (bundle.object_id,)


def test_incompatible_profile_does_not_mutate_member() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _publish_capsule(
            root,
            instance_id="scout-a",
            program_id="incompatible-program",
            portable=False,
        )
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = coordinator.groups()[0]
            for reviewer in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(reviewer),),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle = coordinator.promote(candidate_id=group.candidate_id)

        with HiveField.open(
            root / "member",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="member-a",
            mode="member",
            profile_sha256=sha256_value({"profile": "other"}),
        ) as member:
            assert member.status()["common_generation"] == 0
            assert member.status()["adopted_bundle_ids"] == []
            assert all(row.program_id != "incompatible-program" for row in member.owner.state.programs)
            assert member.preview_imports() == ()


def test_fork_creates_new_instance_lineage() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        source = root / "source"
        with HiveField.open(source, hive_home=root / "hive", mode="isolated", instance_id="source") as field:
            parent_state = field.raw_owner.state.state_sha256
            parent_manifest = field.raw_owner.checkpoints.current_manifest_sha256
        with HiveField.fork(
            source,
            root / "child",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="child",
            mode="isolated",
        ) as child:
            assert child.identity.instance_id == "child"
            assert child.owner.state.state_sha256 == parent_state
            assert child.owner.checkpoints.current_manifest_sha256 == parent_manifest


def test_attach_wraps_existing_owner_boundary() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        owner = FieldIntelligenceOwner(root / "field")

        class OwnerWrapper:
            def __init__(self, wrapped: object) -> None:
                self.owner = wrapped

        try:
            with HiveField.attach(
                OwnerWrapper(owner),
                field_home=root / "field",
                hive_home=root / "hive",
                hive_id="main",
                instance_id="attached",
                mode="isolated",
            ) as field:
                assert field.adapter.owner is owner
                assert field.owner.owner is owner
        finally:
            owner.close()


def test_pytest_fixture_connects_field(hive_field) -> None:
    assert isinstance(hive_field, HiveField)
    assert hive_field.identity.test_name.endswith("test_pytest_fixture_connects_field")
    assert hive_field.policy.export_enabled
    assert hive_field.status()["hive"]["hive_id"] == "main"
    assert hive_field.hive.root == DEFAULT_HIVE_HOME


def test_revoked_bundle_is_blocked_before_owner_mutation() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _publish_capsule(root, instance_id="scout-a", program_id="revoked-program")
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            coordinator = HiveCoordinator(store, leader_instance_id="leader")
            group = coordinator.groups()[0]
            for reviewer in ("reviewer-a", "reviewer-b"):
                coordinator.review(
                    Review(
                        reviewer_instance_id=reviewer,
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(reviewer),),
                    ),
                    candidate_id=group.candidate_id,
                )
            bundle = coordinator.promote(candidate_id=group.candidate_id)
            coordinator.revoke(bundle.object_id, reason="test revocation")
            assert store.is_revoked(bundle.object_id)

        with HiveField.open(
            root / "member",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="member-a",
            mode="member",
        ) as member:
            report = member.sync()
            assert report.blocked == (bundle.object_id,)
            assert report.errors[0]["code"] == "REVOKED_BUNDLE"
            assert member.status()["common_generation"] == 0
            assert all(row.program_id != "revoked-program" for row in member.owner.state.programs)


def test_deterministic_promotion_loop_and_portable_member_adoption() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        profile_a = sha256_value({"profile": "native-a"})
        profile_b = sha256_value({"profile": "native-b"})
        for instance_id, profile_sha256 in (("scout-a", profile_a), ("scout-b", profile_b)):
            with HiveField.open(
                root / instance_id,
                hive_home=root / "hive",
                hive_id="main",
                instance_id=instance_id,
                mode="scout",
                profile_sha256=profile_sha256,
            ) as field:
                program = shared_program("portable-program")
                receipt = field.raw_owner.configure_program(f"{instance_id}:configure", program)
                field.publish_experience(
                    transition=receipt.as_dict(),
                    task_id="portable-program",
                    context={"domain": "portable-test"},
                    action={"operation": "configure-program"},
                    prediction={"program_id": program.program_id},
                    outcome={"status": "configured"},
                    candidate=ExperienceCandidate(
                        kind="field-program",
                        object={"portable_transfer": True, "program": program.as_dict()},
                        operation_plan=(
                            {
                                "operation": "configure-program",
                                "program": program.as_dict(),
                            },
                        ),
                        guards=(),
                        dependencies=(),
                    ),
                    evidence=evidence_for(instance_id),
                )

        with LocalHiveStore(root / "hive", hive_id="main") as store:
            loop = PromotionLoop(
                store,
                leader_instance_id="leader",
                minimum_support_reviews=2,
            )
            groups = loop.coordinator.groups()
            assert len(groups) == 1
            group = groups[0]
            loop.review(
                group.candidate_id,
                (
                    ReviewerDecision("reviewer-a", "supports"),
                    ReviewerDecision("reviewer-b", "supports"),
                ),
            )
            report = loop.run_once()
            assert len(report.promoted_bundle_ids) == 1
            bundle_id = report.promoted_bundle_ids[0]
            assert store.current_generation == 1
            replay = loop.run_once()
            assert replay.promoted_bundle_ids == ()
            assert bundle_id in store.list_bundles()[0].object_id

        with HiveField.open(
            root / "member",
            hive_home=root / "hive",
            hive_id="main",
            instance_id="member",
            mode="member",
            profile_sha256=sha256_value({"profile": "member"}),
        ) as member:
            assert member.status()["common_generation"] == 1
            learned = next(
                row
                for row in member.owner.state.programs
                if row.program_id == "portable-program"
            )
            assert learned.status == "candidate"
