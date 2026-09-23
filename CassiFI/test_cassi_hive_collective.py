from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from cassi_field_atlas import FieldProgram, PrimitiveStep, sha256_value
from cassi_field_hive import Review
from cassi_hive_bridge import SemanticEvent, SemanticEventBridge
from cassi_hive_collective import (
    COLLABORATION_ASSIGNMENT_SCHEMA,
    COLLABORATION_REQUEST_SCHEMA,
    COLLABORATION_RESPONSE_SCHEMA,
    COLLECTIVE_SYNTHESIS_SCHEMA,
    REPRESENTATION_TRANSLATION_SCHEMA,
    AdaptationManager,
    CollectiveHive,
    CollectiveHiveError,
    DiversityProfile,
    CollaborationAssignment,
    CollaborationRequest,
    CollaborationResponse,
    CollectiveSynthesis,
    DiversitySelector,
    HiveOffer,
    HiveQuery,
    HypothesisEdge,
    HypothesisGraph,
    InstanceIdentity,
    ConsolidatedMemory,
    MemoryConsolidator,
    OutcomeEvidence,
    QueryRouter,
    OutcomeMetric,
    PopulationMemberOutcome,
    PopulationOutcomeLedger,
    RepresentationTranslation,
    ExecutableMethod,
    MethodCompositionSpec,
    MethodConnection,
    MethodInterface,
    MethodOutputBinding,
    MethodPort,
    ReviewerProfile,
    ReputationLedger,
    RoleAssignment,
    RoleRouter,
    check_reviewer_independence,
    compose_field_programs,
    weighted_quorum,
)
from cassi_hive_store import LocalHiveStore


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def identity(name: str, *, parent: str | None = None) -> InstanceIdentity:
    return InstanceIdentity.issue(
        instance_id=name,
        secret=(name + "-secret-material").encode("utf-8"),
        source_identity_sha256=digest(name + ":source"),
        configuration_sha256=digest(name + ":config"),
        parent_instance_id=parent,
        issued_ns=1,
    )


def program(program_id: str, *, operation: str = "identity") -> FieldProgram:
    return FieldProgram(
        program_id=program_id,
        version=1,
        roles=("source",),
        steps=(PrimitiveStep(operation=operation, output="result", inputs=("source",)),),
        outputs=("result",),
    )


def test_signed_identity_and_independence_reject_shared_lineage() -> None:
    first = identity("first")
    child_a = identity("child-a", parent="root")
    child_b = identity("child-b", parent="root")
    assert first.verify(b"first-secret-material")
    assert not first.verify(b"wrong-secret-material")
    report = check_reviewer_independence(
        ("first", "child-a", "child-b"),
        {item.instance_id: item for item in (first, child_a, child_b)},
        origin_instance_ids=("first",),
    )
    assert report.accepted_reviewer_ids == ("child-a",)
    assert report.rejected_reviewer_ids == ("first", "child-b")
    assert report.reasons["child-b"] == "shared-identity-lineage-or-configuration"

def test_outcome_evidence_is_control_backed_and_expirable() -> None:
    outcome = OutcomeEvidence(
        bundle_id=digest("bundle"),
        recipient_instance_id="member",
        adoption_receipt_id=digest("receipt"),
        protocol_sha256=digest("protocol"),
        metrics=(OutcomeMetric("accuracy", 0.5, 0.5, 0.8),),
        held_out=True,
        observed_ns=10,
        valid_until_ns=20,
    )
    assert outcome.score == pytest.approx(1.0)
    assert outcome.success
    assert not outcome.expired(now_ns=20)
    assert outcome.expired(now_ns=21)


def test_weighted_quorum_requires_profiles_and_independence() -> None:
    reviewer_a = identity("reviewer-a")
    reviewer_b = identity("reviewer-b")
    profiles = {
        "reviewer-a": ReviewerProfile.virgin("reviewer-a", reviewer_a.attestation_key_sha256),
        "reviewer-b": ReviewerProfile.virgin("reviewer-b", reviewer_b.attestation_key_sha256),
    }
    reviews = (
        Review("reviewer-a", "independent-reproduction", "supports", (digest("a"),)),
        Review("reviewer-b", "adversarial-review", "supports", (digest("b"),)),
    )
    report = weighted_quorum(
        reviews,
        profiles,
        {"reviewer-a": reviewer_a, "reviewer-b": reviewer_b},
        minimum_support_weight=0.9,
        minimum_independent_reviewers=2,
    )
    assert report.accepted
    assert report.support_weight == pytest.approx(1.0)
    missing = weighted_quorum(
        reviews,
        {"reviewer-a": profiles["reviewer-a"]},
        {"reviewer-a": reviewer_a, "reviewer-b": reviewer_b},
        minimum_support_weight=0.5,
        minimum_independent_reviewers=2,
    )
    assert not missing.accepted
    assert missing.reasons["reviewer-b"] == "missing-reputation-profile"



def test_reputation_ledger_calibrates_and_reloads_profiles() -> None:
    with TemporaryDirectory() as tmp:
        store = LocalHiveStore(Path(tmp) / "hive.sqlite3", hive_id="ledger-test")
        try:
            reviewer = identity("calibration-reviewer")
            initial = ReviewerProfile.virgin("calibration-reviewer", reviewer.attestation_key_sha256)
            ledger = ReputationLedger(store)
            ledger.save(initial)
            updated = ledger.update(initial, predicted_support=0.9, actual_success=True)
            reloaded = ledger.load("calibration-reviewer")
            assert reloaded is not None
            assert reloaded.review_count == 1
            assert reloaded.correct_count == 1
            assert reloaded.weight == pytest.approx(updated.weight)
        finally:
            store.close()
def test_hypothesis_graph_preserves_contradiction_branches() -> None:
    graph = HypothesisGraph()
    first = graph.register(candidate_id="candidate-a", branch_id="low-noise", domain="reasoning")
    second = graph.register(candidate_id="candidate-b", branch_id="high-noise", domain="reasoning", parent_hypothesis_id=first.hypothesis_id)
    graph.link(HypothesisEdge(first.hypothesis_id, second.hypothesis_id, "contradicts"))
    assert graph.active(domain="reasoning") == (first, second)
    assert graph.contradictions(first.hypothesis_id) == (second,)

def test_collective_indexes_reload_branches_offers_and_roles() -> None:
    with TemporaryDirectory() as tmp:
        store = LocalHiveStore(Path(tmp) / "hive.sqlite3", hive_id="reload-test")
        try:
            graph = HypothesisGraph(store)
            first = graph.register(candidate_id="candidate-a", branch_id="low-noise", domain="reasoning")
            second = graph.register(
                candidate_id="candidate-b",
                branch_id="high-noise",
                domain="reasoning",
                parent_hypothesis_id=first.hypothesis_id,
            )
            graph.link(HypothesisEdge(first.hypothesis_id, second.hypothesis_id, "contradicts"))
            router = RoleRouter(store)
            router.assign(RoleAssignment("replicator-a", "replicator", ("python",), load=0.2))
            offers = QueryRouter(store)
            offer = HiveOffer(
                offer_id="offer-1",
                provider_instance_id="replicator-a",
                candidate_id="candidate-a",
                kind="program",
                domain="reasoning",
                branch_id="low-noise",
                reliability=0.9,
                work_units=2,
                roles=("replicator",),
            )
            offers.publish(offer)
            reloaded_graph = HypothesisGraph(store)
            reloaded_offers = QueryRouter(store)
            reloaded_roles = RoleRouter(store)
            assert reloaded_graph.contradictions(first.hypothesis_id) == (second,)
            assert reloaded_offers.match(
                HiveQuery("query-1", "requester", domains=("reasoning",), desired_roles=("replicator",))
            ) == (offer,)
            assert reloaded_roles.choose("replicator").instance_id == "replicator-a"
        finally:
            store.close()
def test_collaboration_protocol_is_typed_attributed_and_reloadable() -> None:
    with TemporaryDirectory() as directory:
        path = Path(directory) / "hive.sqlite3"
        with LocalHiveStore(path, hive_id="collaboration") as store:
            collective = CollectiveHive(store)
            request = CollaborationRequest(
                "request-1", "member-a", {"goal": "Reconcile the candidate"},
                ("replicator",), "field-program", "assessment", 2, 8,
                ("candidate-1",),
            )
            assignment = CollaborationAssignment(
                "assignment-1", request.request_id, "member-b", "replicator",
                {"operation": "independent-reproduction"}, "allocation-1",
                ("candidate-1",),
            )
            response = CollaborationResponse(
                "response-1", assignment.assignment_id, "member-b", "completed",
                "field-program", {"finding": "reproduced"},
                ("artifact-1",), ("evidence-1",), (),
            )
            translation = RepresentationTranslation(
                "translation-1", response.response_id, "member-c",
                "field-program", "assessment", {"finding": "reproduced"},
                {"accuracy": "confirmed"}, "validated", (),
            )
            synthesis = CollectiveSynthesis(
                "synthesis-1", request.request_id, "member-a",
                (response.response_id,), (translation.translation_id,),
                {"decision": "adopt"}, ("reproduction",), (),
                ("long-horizon behavior",),
            )
            collective.record_collaboration_request(request)
            collective.record_collaboration_assignment(assignment)
            collective.record_collaboration_response(response)
            collective.record_representation_translation(translation)
            collective.record_collective_synthesis(synthesis)
            with pytest.raises(CollectiveHiveError, match="owner boundary"):
                collective.record_collaboration_assignment(
                    CollaborationAssignment(
                        "bad-assignment", request.request_id, "member-a",
                        "replicator", {"operation": "self-review"},
                        "allocation-1",
                    )
                )
            with pytest.raises(CollectiveHiveError, match="assigned owner"):
                collective.record_collaboration_response(
                    CollaborationResponse(
                        "bad-response", assignment.assignment_id, "member-c",
                        "completed", "assessment", {"finding": "unauthorized"},
                    )
                )
        with LocalHiveStore(path, hive_id="collaboration") as reloaded_store:
            reloaded = CollectiveHive(reloaded_store)
            expected = {
                COLLABORATION_REQUEST_SCHEMA: request.as_dict(),
                COLLABORATION_ASSIGNMENT_SCHEMA: assignment.as_dict(),
                COLLABORATION_RESPONSE_SCHEMA: response.as_dict(),
                REPRESENTATION_TRANSLATION_SCHEMA: translation.as_dict(),
                COLLECTIVE_SYNTHESIS_SCHEMA: synthesis.as_dict(),
            }
            for schema, content in expected.items():
                documents = reloaded.list_collaboration(schema)
                assert len(documents) == 1
                assert documents[0]["content"] == content


def test_collaborative_partial_methods_compile_execute_and_expose_gaps() -> None:
    required_interface = MethodInterface(
        inputs=(
            MethodPort("reading", "scalar", "sensor", "C"),
        ),
        outputs=(
            MethodPort("safe", "boolean", "decision", "1"),
        ),
    )
    normalize = ExecutableMethod(
        program=FieldProgram(
            program_id="normalize-temperature",
            version=3,
            roles=("raw_c",),
            steps=(
                PrimitiveStep(
                    operation="constant",
                    output="offset",
                    literal=273.15,
                ),
                PrimitiveStep(
                    operation="add",
                    output="kelvin",
                    inputs=("raw_c", "offset"),
                ),
            ),
            outputs=("kelvin",),
        ),
        interface=MethodInterface(
            inputs=(
                MethodPort("reading", "scalar", "sensor", "C", "raw_c"),
            ),
            outputs=(
                MethodPort(
                    "temperature",
                    "scalar",
                    "thermodynamic",
                    "K",
                    "kelvin",
                ),
            ),
        ),
        assumptions=({"scale": "Celsius"},),
        effects=("normalizes-temperature",),
        maximum_work=2,
        uncertainty=0.01,
        correction_ids=("calibration-correction-3",),
    )
    classify = ExecutableMethod(
        program=FieldProgram(
            program_id="classify-temperature",
            version=2,
            roles=("temperature_k",),
            steps=(
                PrimitiveStep(
                    operation="constant",
                    output="limit_k",
                    literal=310.0,
                ),
                PrimitiveStep(
                    operation="less_equal",
                    output="within_limit",
                    inputs=("temperature_k", "limit_k"),
                ),
            ),
            outputs=("within_limit",),
        ),
        interface=MethodInterface(
            inputs=(
                MethodPort(
                    "temperature",
                    "scalar",
                    "thermodynamic",
                    "K",
                    "temperature_k",
                ),
            ),
            outputs=(
                MethodPort(
                    "safe",
                    "boolean",
                    "decision",
                    "1",
                    "within_limit",
                ),
            ),
        ),
        preconditions=({"temperature_k": {"minimum": 0.0}},),
        effects=("classifies-temperature",),
        maximum_work=2,
        uncertainty=0.02,
    )
    with TemporaryDirectory() as directory:
        path = Path(directory) / "hive.sqlite3"
        with LocalHiveStore(path, hive_id="method-composition") as store:
            collective = CollectiveHive(store)
            request = CollaborationRequest(
                "request-method",
                "root",
                {"goal": "normalize and classify a temperature"},
                ("translator", "operator"),
                "sensor",
                "decision",
                2,
                8,
                required_interface=required_interface,
            )
            first_assignment = CollaborationAssignment(
                "assignment-normalize",
                request.request_id,
                "member-normalize",
                "translator",
                {"operation": "normalize"},
                "allocation-normalize",
            )
            second_assignment = CollaborationAssignment(
                "assignment-classify",
                request.request_id,
                "member-classify",
                "operator",
                {"operation": "classify"},
                "allocation-classify",
            )
            first_response = CollaborationResponse(
                "response-normalize",
                first_assignment.assignment_id,
                first_assignment.assignee_instance_id,
                "completed",
                "thermodynamic",
                {"finding": "normalization available"},
                method=normalize,
            )
            second_response = CollaborationResponse(
                "response-classify",
                second_assignment.assignment_id,
                second_assignment.assignee_instance_id,
                "completed",
                "decision",
                {"finding": "classification available"},
                method=classify,
            )
            collective.record_collaboration_request(request)
            collective.record_collaboration_assignment(first_assignment)
            collective.record_collaboration_assignment(second_assignment)
            collective.record_collaboration_response(first_response)
            collective.record_collaboration_response(second_response)
            composition = MethodCompositionSpec(
                program_id="temperature-safety",
                component_ids=(
                    first_response.response_id,
                    second_response.response_id,
                ),
                connections=(
                    MethodConnection(
                        "$request",
                        "reading",
                        first_response.response_id,
                        "reading",
                    ),
                    MethodConnection(
                        first_response.response_id,
                        "temperature",
                        second_response.response_id,
                        "temperature",
                    ),
                ),
                outputs=(
                    MethodOutputBinding(
                        "safe",
                        second_response.response_id,
                        "safe",
                    ),
                ),
                maximum_work=5,
            )
            synthesis = CollectiveSynthesis(
                "synthesis-method",
                request.request_id,
                "root",
                (first_response.response_id, second_response.response_id),
                (),
                {"decision": "compose"},
                composition=composition,
            )
            collective.record_collective_synthesis(synthesis)
            compiled = collective.compile_collective_synthesis(synthesis)
            assert compiled.gaps == ()
            assert compiled.method is not None
            assert compiled.method.execute({"reading": 20.0}) == {"safe": True}
            assert {
                row["origin_instance_id"] for row in compiled.provenance
            } == {"member-normalize", "member-classify"}
            assert compiled.method.correction_ids == (
                "calibration-correction-3",
            )

            gap_synthesis = CollectiveSynthesis(
                "synthesis-gap",
                request.request_id,
                "root",
                (second_response.response_id,),
                (),
                {"decision": "retain gap"},
                composition=MethodCompositionSpec(
                    program_id="temperature-gap",
                    component_ids=(second_response.response_id,),
                    connections=(),
                    outputs=(
                        MethodOutputBinding(
                            "safe",
                            second_response.response_id,
                            "safe",
                        ),
                    ),
                    maximum_work=3,
                ),
            )
            collective.record_collective_synthesis(gap_synthesis)
            gap = collective.compile_collective_synthesis(gap_synthesis)
            assert gap.method is None
            assert gap.gaps[0]["kind"] == "missing-input-binding"

            incompatible = CollectiveSynthesis(
                "synthesis-incompatible",
                request.request_id,
                "root",
                (second_response.response_id,),
                (),
                {"decision": "reject"},
                composition=MethodCompositionSpec(
                    program_id="temperature-incompatible",
                    component_ids=(second_response.response_id,),
                    connections=(
                        MethodConnection(
                            "$request",
                            "reading",
                            second_response.response_id,
                            "temperature",
                        ),
                    ),
                    outputs=(
                        MethodOutputBinding(
                            "safe",
                            second_response.response_id,
                            "safe",
                        ),
                    ),
                    maximum_work=3,
                ),
            )
            with pytest.raises(CollectiveHiveError, match="incompatible"):
                collective.record_collective_synthesis(incompatible)
        with LocalHiveStore(path, hive_id="method-composition") as store:
            reloaded = CollectiveHive(store)
            rebuilt = reloaded.compile_collective_synthesis(synthesis)
            assert rebuilt.method is not None
            assert rebuilt.method.execute({"reading": 40.0}) == {"safe": False}



def test_query_router_matches_demand_to_specialized_offer() -> None:
    with TemporaryDirectory() as directory:
        with LocalHiveStore(Path(directory) / "hive", hive_id="main") as store:
            collective = CollectiveHive(store)
            collective.publish_offer(HiveOffer("offer-a", "scout-a", "candidate-a", "field-program", "reasoning", "main", 0.9, 12, ("replicator",)))
            collective.publish_offer(HiveOffer("offer-b", "scout-b", "candidate-b", "procedure", "physics", "main", 0.95, 4, ("operator",)))
            query = HiveQuery("query", "member", kinds=("field-program",), domains=("reasoning",), minimum_reliability=0.8, desired_roles=("replicator",))
            assert collective.record_query(query) == "query"
            assert collective.router.match(query)[0].offer_id == "offer-a"


def test_diversity_selector_keeps_different_profiles() -> None:
    items = ["a", "b", "c"]
    profiles = {
        "a": DiversityProfile("a", digest("profile-a"), "reasoning", "branch-a", 1),
        "b": DiversityProfile("b", digest("profile-a"), "reasoning", "branch-a", 2),
        "c": DiversityProfile("c", digest("profile-c"), "physics", "branch-c", 3),
    }
    selected = DiversitySelector.select(items, profiles, limit=2)
    assert selected == ("a", "c")


def test_specialist_router_assigns_least_loaded_capable_instance() -> None:
    router = RoleRouter()
    router.assign(RoleAssignment("replicator-a", "replicator", ("python",), load=0.8))
    router.assign(RoleAssignment("replicator-b", "replicator", ("python", "gpu"), load=0.2))
    assert router.choose("replicator", ("gpu",)).instance_id == "replicator-b"


def test_composed_program_is_typed_and_bounded() -> None:
    first = program("first")
    second = FieldProgram(
        program_id="second",
        version=1,
        roles=("result",),
        steps=(PrimitiveStep(operation="identity", output="final", inputs=("result",)),),
        outputs=("final",),
    )
    composed = compose_field_programs((first, second), program_id="composed")
    assert composed.execute({"source": 7}) == {"second:final": 7}
    assert "first" in composed.dependencies
    with pytest.raises(CollectiveHiveError):
        compose_field_programs((first, second), program_id="too-small", maximum_steps=1)


def test_local_adaptation_and_memory_consolidation_persist() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        with LocalHiveStore(root / "hive", hive_id="main") as store:
            collective = CollectiveHive(store)
            fork = collective.adaptations.propose(
                parent_bundle_id=digest("bundle"),
                instance_id="member",
                parent_profile_sha256=digest("parent-profile"),
                local_profile_sha256=digest("local-profile"),
                changes={"guard": "high-noise"},
            )
            assert store.has_object(fork.object_id)
            assert fork.status == "proposed"


def test_consolidated_memory_expiration_is_explicit() -> None:
    memory = ConsolidatedMemory(
        memory_id=digest("memory"),
        candidate_id="candidate",
        source_experience_ids=(digest("source"),),
        source_count=1,
        domain_coverage=("reasoning",),
        best_score=0.8,
        valid_until_ns=10,
    )
    expired = MemoryConsolidator().expire((memory,), now_ns=11)
    assert len(expired) == 1
    assert expired[0].memory_id == memory.memory_id

def test_bridge_emits_bounded_causally_linked_events() -> None:
    bridge = SemanticEventBridge()
    event = bridge.emit_outcome(
        source_instance_id="member",
        bundle_id=digest("bundle"),
        outcome={"score": 0.8},
        causality_ids=(digest("receipt"),),
    )
    assert isinstance(event, SemanticEvent)
    assert event.cassicore_payload()["type"] == "cassi.hive.adoption-outcome"
    assert event.cosmos_payload()["cmd"] == "snapshot"
    assert bridge.events == [event]


def test_bridge_emits_population_outcome_event() -> None:
    bridge = SemanticEventBridge()
    event = bridge.emit_population(
        source_instance_id="population-rollout",
        bundle_id=digest("bundle"),
        ledger={"status": "accepted", "member_count": 3},
        causality_ids=(digest("outcome-a"), digest("outcome-b")),
    )
    assert event.cassicore_payload()["type"] == "cassi.hive.population-outcome"
    assert event.content["payload"]["ledger"]["member_count"] == 3
    assert bridge.events == [event]


def test_collective_facade_records_identity_and_outcome() -> None:
    with TemporaryDirectory() as directory:
        with LocalHiveStore(Path(directory) / "hive", hive_id="main") as store:
            collective = CollectiveHive(store)
            manifest = identity("member")
            assert collective.record_identity(manifest) == manifest.object_id
            outcome = OutcomeEvidence(
                bundle_id=digest("bundle"),
                recipient_instance_id="member",
                adoption_receipt_id=digest("receipt"),
                protocol_sha256=digest("protocol"),
                metrics=(OutcomeMetric("loss", 1.0, 1.0, 0.5, higher_is_better=False),),
                held_out=True,
            )
            assert collective.record_outcome(outcome) == outcome.object_id
            assert store.has_object(outcome.object_id)
            member = PopulationMemberOutcome(
                instance_id="member",
                field_profile_sha256=digest("profile"),
                adoption_status="accepted",
                outcome_success=True,
                score=0.8,
                adoption_receipt_id=digest("receipt"),
                outcome_id=outcome.object_id,
                adopted_program_ids=("program",),
                post_state_sha256=digest("state"),
                report={"applied": [digest("bundle")]},
            )
            ledger = PopulationOutcomeLedger(
                bundle_id=digest("bundle"),
                protocol_sha256=digest("protocol"),
                members=(member,),
                created_ns=1,
            )
            assert collective.record_population_ledger(ledger) == ledger.object_id
            assert collective.list_population_ledgers()[0]["object_id"] == ledger.object_id
