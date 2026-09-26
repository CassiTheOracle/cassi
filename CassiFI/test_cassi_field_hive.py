from __future__ import annotations

import hashlib
import math
from dataclasses import replace
from tempfile import TemporaryDirectory
from typing import Any

import pytest
from cassi_field_cognition import FieldIntelligenceError
from cassi_field_atlas import FieldProgram, PrimitiveStep, RelationChart, VariableSpec
from cassi_field_hive import (
    AdoptionReceipt,
    ExperienceCandidate,
    ExperienceCapsule,
    ExperienceEpisode,
    ExperienceEvidence,
    ExperienceOrigin,
    HiveProtocolError,
    Review,
    TransferSpec,
    admit_bundle,
    apply_bundle_to_owner,
    build_knowledge_bundle,
    capsule_from_owner_transition,
    verify_object_digest,
)
from cassi_field_owner import FieldIntelligenceOwner, SourceInput
from run_field_intelligence_scenario import _admit_pair, _configure, _source


def digest(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()
def capsule(instance_id: str = "scout-a") -> ExperienceCapsule:
    profile = digest("field-profile")
    return ExperienceCapsule(
        hive_id="hive-test",
        origin=ExperienceOrigin(
            instance_id=instance_id,
            role="scout",
            field_profile_sha256=profile,
            atlas_schema="cassifi.field-atlas.v2",
            predecessor_manifest_sha256=digest(f"{instance_id}:manifest:0"),
            predecessor_state_sha256=digest(f"{instance_id}:state:0"),
            successor_manifest_sha256=digest(f"{instance_id}:manifest:1"),
            successor_state_sha256=digest(f"{instance_id}:state:1"),
            local_generation=1,
            common_generation=0,
        ),
        episode=ExperienceEpisode(
            task_id="task-1",
            context={"regime": "calm"},
            source_revision_ids=(digest("source-1"),),
            observation_event_ids=(digest("event-1"),),
            action={"operation": "observe"},
            prediction={"next": 1},
            outcome={"next": 1},
            work_units=4,
            uncertainty=0.1,
        ),
        candidate=ExperienceCandidate(
            kind="field-program",
            object={"program_id": "program-1", "version": 1},
            operation_plan=({"operation": "add-program", "program_id": "program-1"},),
            guards=({"field": "regime", "operator": "equals", "value": "calm"},),
            dependencies=(),
        ),
        evidence=ExperienceEvidence(
            support_event_ids=(digest("event-1"),),
            assessment_ids=(digest("assessment-1"),),
            held_out_results=({"loss": 0.0},),
            counterexamples=(),
            derivation_roots=(),
        ),
        transfer=TransferSpec(
            required_field_profile_sha256=profile,
            required_atlas_schema="cassifi.field-atlas.v2",
            replay_mode="semantic",
            maximum_admission_work=32,
            visibility="public",
        ),
    )


def learn_relative_program(
    owner: FieldIntelligenceOwner,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    tuple[str, ...],
    tuple[str, ...],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
]:
    _configure(owner)
    baseline_pairs = (
        (-4.0, -1.0),
        (-3.0, 2.0),
        (-2.0, -5.0),
        (-1.0, 4.0),
        (0.0, 3.0),
        (1.0, -3.0),
        (2.0, 5.0),
        (3.0, 0.0),
    )
    event_ids: list[str] = []
    support_witnesses: list[dict[str, Any]] = []
    sequence = 0
    for index, (source_position, destination_position) in enumerate(baseline_pairs):
        sequence += 1
        admitted = _admit_pair(
            owner,
            operation_id=f"hive:learn:baseline:{index}",
            source_position=source_position,
            destination_position=destination_position,
            sequence=sequence,
        )
        event_ids.append(admitted["event"]["event_id"])
        if index < 2:
            event = admitted["event"]
            support_witnesses.append(
                {
                    "context": dict(event["context"]),
                    "derivation_roots": list(event["derivation_roots"]),
                    "event_kind": event["event_kind"],
                    "epistemic_type": event["epistemic_type"],
                    "source": dict(
                        _source(
                            f"episode:hive:learn:baseline:{index}",
                            {
                                "destination": destination_position,
                                "source": source_position,
                            },
                            sequence=sequence,
                        ).as_dict()
                    ),
                    "values": dict(event["values"]),
                }
            )

    candidates = owner.propose_relational_structure(
        operation_id="hive:learn:propose",
        problem_id="relative-position",
        input_roles=("source", "destination"),
        output_role="displacement",
        support_event_ids=tuple(event_ids[:2]),
        max_candidates=9,
    )["candidate_ids"]

    assessment_ids: list[str] = []
    assessment_witnesses: list[dict[str, Any]] = []
    last_admitted: dict[str, Any] = {}
    for episode_index, (source_position, destination_position) in enumerate(
        ((1.0, 4.0), (2.0, 6.0), (-2.0, 3.0))
    ):
        frozen: dict[str, str] = {}
        for candidate_index, candidate_id in enumerate((candidates[-1],)):
            begun = owner.begin_program_assessment(
                operation_id=f"hive:learn:begin:{episode_index}:{candidate_index}",
                program_id=candidate_id,
                bindings={
                    "destination": destination_position,
                    "source": source_position,
                },
            )
            frozen[candidate_id] = begun["prediction"]["prediction_id"]
        sequence += 1
        last_admitted = dict(
            _admit_pair(
                owner,
                operation_id=f"hive:learn:future:{episode_index}",
                source_position=source_position,
                destination_position=destination_position,
                sequence=sequence,
            )
        )
        event = last_admitted["event"]
        assessment_witnesses.append(
            {
                "bindings": {
                    "destination": destination_position,
                    "source": source_position,
                },
                "context": dict(event["context"]),
                "derivation_roots": list(event["derivation_roots"]),
                "event_kind": event["event_kind"],
                "epistemic_type": event["epistemic_type"],
                "loss_scale": 10.0,
                "outcome": {
                    "displacement": destination_position - source_position,
                },
                "source": dict(
                    _source(
                        f"episode:hive:learn:future:{episode_index}",
                        {
                            "destination": destination_position,
                            "source": source_position,
                        },
                        sequence=sequence,
                    ).as_dict()
                ),
                "values": dict(event["values"]),
            }
        )
        for candidate_index, candidate_id in enumerate((candidates[-1],)):
            resolved = owner.resolve_program_assessment(
                operation_id=f"hive:learn:resolve:{episode_index}:{candidate_index}",
                program_id=candidate_id,
                prediction_id=frozen[candidate_id],
                outcome={"displacement": destination_position - source_position},
                event_id=last_admitted["event"]["event_id"],
                loss_scale=10.0,
            )
            assessment = resolved["assessment"]
            assessment_witnesses[-1]["resolution_floor"] = assessment[
                "resolution_floor"
            ]
            assessment_witnesses[-1]["resolution_status"] = assessment[
                "resolution_status"
            ]
            assessment_ids.append(assessment["assessment_id"])

    promoted = owner.promote_program(
        operation_id="hive:learn:promote",
        candidate_ids=(candidates[-1],),
        minimum_assessments=3,
        maximum_average_loss=1e-12,
        bit_penalty=1e-6,
    )
    return (
        dict(promoted["program"]),
        dict(promoted["receipt"]),
        last_admitted,
        tuple(event_ids),
        tuple(assessment_ids),
        tuple(support_witnesses),
        tuple(assessment_witnesses),
    )

def learn_role_identity_program(
    owner: FieldIntelligenceOwner,
    *,
    input_role: str,
    output_role: str,
    prefix: str,
    heldout_value: float,
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    dict[str, Any],
]:
    owner.configure_variable(
        f"hive:learn:{prefix}:variable",
        VariableSpec(output_role, unit="m", lower=-20.0, upper=20.0),
    )

    def values_for(value: float) -> dict[str, float]:
        source = value if input_role == "source" else value - 1.0
        destination = value + 1.0 if input_role == "source" else value
        return {
            "bias": 1.0,
            "source": source,
            "destination": destination,
            "displacement": destination - source,
            "left_score": source - destination,
            "right_score": destination - source,
            output_role: value,
        }

    def payload_for(value: float) -> dict[str, float]:
        values = values_for(value)
        return {"source": values["source"], "destination": values["destination"]}

    baseline = (-4.0, -1.0, 2.0, 5.0)
    event_ids: list[str] = []
    support_witnesses: list[dict[str, Any]] = []
    sequence = 300
    for index, value in enumerate(baseline):
        sequence += 1
        source_payload = payload_for(value)
        admitted = owner.admit_observation(
            operation_id=f"hive:learn:{prefix}:baseline:{index}",
            source=_source(
                f"episode:hive:learn:{prefix}:baseline:{index}",
                source_payload,
                sequence=sequence,
            ),
            values=values_for(value),
            context={"domain": "language", "quality": "controlled"},
        )
        event = admitted["event"]
        event_ids.append(event["event_id"])
        if index < 2:
            support_witnesses.append(
                {
                    "context": dict(event["context"]),
                    "derivation_roots": list(event["derivation_roots"]),
                    "event_kind": event["event_kind"],
                    "epistemic_type": event["epistemic_type"],
                    "source": dict(
                        _source(
                            f"episode:hive:learn:{prefix}:baseline:{index}",
                            source_payload,
                            sequence=sequence,
                        ).as_dict()
                    ),
                    "values": dict(event["values"]),
                }
            )
    candidates = owner.propose_relational_structure(
        operation_id=f"hive:learn:{prefix}:propose",
        problem_id=f"language-{input_role}-identity",
        input_roles=(input_role,),
        output_role=output_role,
        support_event_ids=tuple(event_ids[:2]),
        max_candidates=3,
    )["candidate_ids"]
    candidate_id = candidates[0]
    assessment_witnesses: list[dict[str, Any]] = []
    for index, value in enumerate((1.0, 3.0, -2.0)):
        begun = owner.begin_program_assessment(
            operation_id=f"hive:learn:{prefix}:begin:{index}",
            program_id=candidate_id,
            bindings={input_role: value},
        )
        sequence += 1
        source_payload = payload_for(value)
        admitted = owner.admit_observation(
            operation_id=f"hive:learn:{prefix}:future:{index}",
            source=_source(
                f"episode:hive:learn:{prefix}:future:{index}",
                source_payload,
                sequence=sequence,
            ),
            values=values_for(value),
            context={"domain": "language", "quality": "controlled"},
        )
        event = admitted["event"]
        assessment_witnesses.append(
            {
                "bindings": {input_role: value},
                "context": dict(event["context"]),
                "derivation_roots": list(event["derivation_roots"]),
                "event_kind": event["event_kind"],
                "epistemic_type": event["epistemic_type"],
                "loss_scale": 1.0,
                "outcome": {output_role: value},
                "source": dict(
                    _source(
                        f"episode:hive:learn:{prefix}:future:{index}",
                        source_payload,
                        sequence=sequence,
                    ).as_dict()
                ),
                "values": dict(event["values"]),
            }
        )
        resolved = owner.resolve_program_assessment(
            operation_id=f"hive:learn:{prefix}:resolve:{index}",
            program_id=candidate_id,
            prediction_id=begun["prediction"]["prediction_id"],
            outcome={output_role: value},
            event_id=event["event_id"],
            loss_scale=1.0,
        )
        assessment = resolved["assessment"]
        assessment_witnesses[-1]["resolution_floor"] = assessment[
            "resolution_floor"
        ]
        assessment_witnesses[-1]["resolution_status"] = assessment[
            "resolution_status"
        ]
    promoted = owner.promote_program(
        operation_id=f"hive:learn:{prefix}:promote",
        candidate_ids=(candidate_id,),
        minimum_assessments=3,
        maximum_average_loss=1e-12,
        bit_penalty=1e-6,
    )
    sequence += 1
    source_payload = payload_for(heldout_value)
    heldout = owner.admit_observation(
        operation_id=f"hive:learn:{prefix}:heldout",
        source=_source(
            f"episode:hive:learn:{prefix}:heldout",
            source_payload,
            sequence=sequence,
        ),
        values=values_for(heldout_value),
        context={"domain": "language", "quality": "held-out"},
    )
    event = heldout["event"]
    heldout_witness = {
        "bindings": {input_role: heldout_value},
        "context": dict(event["context"]),
        "derivation_roots": list(event["derivation_roots"]),
        "event_kind": event["event_kind"],
        "epistemic_type": event["epistemic_type"],
        "loss_scale": 1.0,
        "outcome": {output_role: heldout_value},
        "source": dict(
            _source(
                f"episode:hive:learn:{prefix}:heldout",
                source_payload,
                sequence=sequence,
            ).as_dict()
        ),
        "values": dict(event["values"]),
    }
    candidate_payload = dict(promoted["program"])
    candidate_payload["status"] = "candidate"
    candidate_payload["version"] = 1
    candidate_payload["assessments"] = []
    return (
        candidate_payload,
        dict(heldout["receipt"]),
        tuple(support_witnesses),
        tuple(assessment_witnesses),
        heldout_witness,
    )


def compose_language_program(
    owner: FieldIntelligenceOwner,
    *,
    frontier_program_ids: tuple[str, ...],
    support_witnesses: tuple[dict[str, Any], ...],
) -> tuple[
    dict[str, Any],
    dict[str, Any],
    tuple[dict[str, Any], ...],
    tuple[dict[str, Any], ...],
    dict[str, Any],
]:
    proposal = owner.propose_program_compositions(
        operation_id="hive:learn:language:compose:frontier",
        problem_id="language.relocation.frontier",
        program_ids=frontier_program_ids,
        minimum_components=2,
        maximum_components=3,
        maximum_candidates=8,
        maximum_steps=3,
        maximum_prefix_code_bits=256,
    )
    candidate_ids = tuple(proposal["candidate_ids"])
    assert len(candidate_ids) == 8
    assessment_witnesses_by_candidate: dict[
        str, tuple[dict[str, Any], ...]
    ] = {}
    sequence = 500
    for candidate_id in candidate_ids:
        candidate = owner.state.program(candidate_id)
        candidate_witnesses: list[dict[str, Any]] = []
        for index, (source, destination) in enumerate(
            ((1.0, 4.0), (2.0, 6.0), (-2.0, 3.0))
        ):
            bindings = {
                role: {"source": source, "destination": destination}[role]
                for role in candidate.roles
            }
            begun = owner.begin_program_assessment(
                operation_id=f"hive:learn:language:compose:begin:{candidate_id}:{index}",
                program_id=candidate_id,
                bindings=bindings,
            )
            sequence += 1
            values = {
                "bias": 1.0,
                "source": source,
                "destination": destination,
                "displacement": destination - source,
                "left_score": source - destination,
                "source_scaled": source,
                "destination_scaled": destination,
                "source_drift": source,
                "source_value": source,
                "destination_value": destination,
            }
            source_payload = {"destination": destination, "source": source}
            admitted = owner.admit_observation(
                operation_id=f"hive:learn:language:compose:future:{candidate_id}:{index}",
                source=_source(
                    f"episode:hive:learn:language:compose:future:{candidate_id}:{index}",
                    source_payload,
                    sequence=sequence,
                ),
                values=values,
                context={"domain": "language", "quality": "controlled"},
            )
            event = admitted["event"]
            outcome = {name: values[name] for name in candidate.outputs}
            candidate_witnesses.append(
                {
                    "bindings": dict(bindings),
                    "context": dict(event["context"]),
                    "derivation_roots": list(event["derivation_roots"]),
                    "event_kind": event["event_kind"],
                    "epistemic_type": event["epistemic_type"],
                    "loss_scale": 1.0,
                    "outcome": outcome,
                    "source": dict(
                        _source(
                            f"episode:hive:learn:language:compose:future:{candidate_id}:{index}",
                            source_payload,
                            sequence=sequence,
                        ).as_dict()
                    ),
                    "values": dict(event["values"]),
                }
            )
            resolved = owner.resolve_program_assessment(
                operation_id=f"hive:learn:language:compose:resolve:{candidate_id}:{index}",
                program_id=candidate_id,
                prediction_id=begun["prediction"]["prediction_id"],
                outcome=outcome,
                event_id=event["event_id"],
                loss_scale=1.0,
            )
            assessment = resolved["assessment"]
            candidate_witnesses[-1]["resolution_floor"] = assessment[
                "resolution_floor"
            ]
            candidate_witnesses[-1]["resolution_status"] = assessment[
                "resolution_status"
            ]
        assessment_witnesses_by_candidate[candidate_id] = tuple(candidate_witnesses)
    promoted = owner.promote_program(
        operation_id="hive:learn:language:compose:promote",
        candidate_ids=candidate_ids,
        minimum_assessments=3,
        maximum_average_loss=1e-12,
        bit_penalty=1e-6,
    )
    assert promoted["program"]["program_id"] == candidate_ids[0]
    rejected_distractors = tuple(
        owner.state.program(candidate_id) for candidate_id in candidate_ids[1:4]
    )
    assert all(
        0.0 < program.prequential_loss < 1.0
        for program in rejected_distractors
    )
    heldout_source, heldout_destination = 4.0, 9.0
    sequence += 1
    heldout_values = {
        "bias": 1.0,
        "source": heldout_source,
        "destination": heldout_destination,
        "displacement": heldout_destination - heldout_source,
        "left_score": heldout_source - heldout_destination,
        "right_score": heldout_destination - heldout_source,
        "source_value": heldout_source,
        "destination_value": heldout_destination,
        "source_scaled": heldout_source,
        "destination_scaled": heldout_destination,
        "source_drift": heldout_source,
    }
    heldout_payload = {
        "destination": heldout_destination,
        "source": heldout_source,
    }
    heldout = owner.admit_observation(
        operation_id="hive:learn:language:compose:heldout",
        source=_source(
            "episode:hive:learn:language:compose:heldout",
            heldout_payload,
            sequence=sequence,
        ),
        values=heldout_values,
        context={"domain": "language", "quality": "held-out"},
    )
    event = heldout["event"]
    heldout_witness = {
        "bindings": {
            "destination": heldout_destination,
            "source": heldout_source,
        },
        "context": dict(event["context"]),
        "derivation_roots": list(event["derivation_roots"]),
        "event_kind": event["event_kind"],
        "epistemic_type": event["epistemic_type"],
        "loss_scale": 1.0,
        "outcome": {
            "source_value": heldout_source,
            "destination_value": heldout_destination,
        },
        "source": dict(
            _source(
                "episode:hive:learn:language:compose:heldout",
                heldout_payload,
                sequence=sequence,
            ).as_dict()
        ),
        "values": dict(event["values"]),
    }
    candidate_payload = dict(promoted["program"])
    candidate_payload["status"] = "candidate"
    candidate_payload["version"] = 1
    candidate_payload["assessments"] = []
    return (
        candidate_payload,
        dict(heldout["receipt"]),
        tuple(support_witnesses),
        assessment_witnesses_by_candidate[candidate_payload["program_id"]],
        heldout_witness,
    )


def reviews() -> tuple[Review, Review]:
    return (
        Review(
            reviewer_instance_id="reviewer-b",
            review_type="independent-reproduction",
            result="supports",
            evidence_ids=(digest("review-b"),),
        ),
        Review(
            reviewer_instance_id="reviewer-c",
            review_type="adversarial-review",
            result="supports",
            evidence_ids=(digest("review-c"),),
        ),
    )


def test_hive_objects_are_content_addressed_and_mutation_visible() -> None:
    first = capsule()
    second = capsule()

    assert first.object_id == second.object_id
    serialized = first.as_dict()
    assert verify_object_digest(serialized)

    mutated = dict(serialized)
    mutated_content = dict(mutated["content"])
    mutated_content["hive_id"] = "other-hive"
    mutated["content"] = mutated_content
    assert not verify_object_digest(mutated)

    with pytest.raises(TypeError):
        first.candidate.object["new"] = "value"  # type: ignore[index]


def test_bundle_requires_independent_support_and_preserves_lineage() -> None:
    source = capsule()
    bundle = build_knowledge_bundle(
        (source,),
        leader_instance_id="leader",
        authority_grant_sha256=digest("grant"),
        predecessor_common_generation=0,
        reviews=reviews(),
        minimum_support_reviews=2,
    )

    assert bundle.predecessor_common_generation == 0
    assert bundle.resulting_common_generation == 1
    assert bundle.source_experience_ids == (source.object_id,)
    assert verify_object_digest(bundle.as_dict())

    with pytest.raises(HiveProtocolError, match="own capsule"):
        build_knowledge_bundle(
            (source,),
            leader_instance_id="leader",
            authority_grant_sha256=digest("grant"),
            predecessor_common_generation=0,
            reviews=(
                Review(
                    reviewer_instance_id="scout-a",
                    review_type="independent-reproduction",
                    result="supports",
                    evidence_ids=(digest("invalid-review"),),
                ),
            ),
        )


def test_admission_accepts_valid_successor_and_rejects_wrong_profile_without_mutation() -> None:
    source = capsule()
    bundle = build_knowledge_bundle(
        (source,),
        leader_instance_id="leader",
        authority_grant_sha256=digest("grant"),
        predecessor_common_generation=0,
        reviews=reviews(),
    )
    predecessor_manifest = digest("recipient-manifest-0")
    predecessor_state = digest("recipient-state-0")
    successor_manifest = digest("recipient-manifest-1")
    successor_state = digest("recipient-state-1")

    accepted = admit_bundle(
        bundle,
        recipient_instance_id="recipient",
        field_profile_sha256=digest("field-profile"),
        atlas_schema="cassifi.field-atlas.v2",
        current_common_generation=0,
        predecessor_manifest_sha256=predecessor_manifest,
        predecessor_state_sha256=predecessor_state,
        successor_manifest_sha256=successor_manifest,
        successor_state_sha256=successor_state,
        applied_object_ids=("program-1",),
        baseline_observation_ids=(digest("baseline"),),
        post_adoption_observation_ids=(digest("after"),),
        behavioral_delta={"selection_changed": True},
        field_effect_confirmed=True,
    )

    assert isinstance(accepted, AdoptionReceipt)
    assert accepted.status == "accepted"
    assert accepted.successor_state_sha256 == successor_state
    assert accepted.field_effect_confirmed
    assert verify_object_digest(accepted.as_dict())

    incompatible = admit_bundle(
        bundle,
        recipient_instance_id="recipient",
        field_profile_sha256=digest("wrong-profile"),
        atlas_schema="cassifi.field-atlas.v2",
        current_common_generation=0,
        predecessor_manifest_sha256=predecessor_manifest,
        predecessor_state_sha256=predecessor_state,
        successor_manifest_sha256=successor_manifest,
        successor_state_sha256=successor_state,
    )

    assert incompatible.status == "incompatible"
    assert incompatible.successor_state_sha256 == predecessor_state
    assert incompatible.applied_object_ids == ()


def test_admission_rejects_stale_common_generation() -> None:
    source = capsule()
    bundle = build_knowledge_bundle(
        (source,),
        leader_instance_id="leader",
        authority_grant_sha256=digest("grant"),
        predecessor_common_generation=0,
        reviews=reviews(),
    )

    result = admit_bundle(
        bundle,
        recipient_instance_id="recipient",
        field_profile_sha256=digest("field-profile"),
        atlas_schema="cassifi.field-atlas.v2",
        current_common_generation=1,
        predecessor_manifest_sha256=digest("recipient-manifest-0"),
        predecessor_state_sha256=digest("recipient-state-0"),
    )

    assert result.status == "incompatible"
    assert result.resulting_common_generation == 1
    assert result.successor_state_sha256 == result.predecessor_state_sha256


def test_real_owner_capsule_and_bundle_reach_an_independent_recipient() -> None:
    profile = digest("owner-field-profile")
    program_id = "hive.shared.identity"
    with TemporaryDirectory() as directory:
        root = __import__("pathlib").Path(directory)
        owner_a = FieldIntelligenceOwner(root / "a")
        owner_b = FieldIntelligenceOwner(root / "b")
        owner_c = FieldIntelligenceOwner(root / "c")
        try:
            owner_a.configure_variable(
                "hive:configure-variable:a",
                VariableSpec("x", lower=-100.0, upper=100.0),
            )
            owner_a.configure_chart(
                "hive:configure-chart:a",
                RelationChart.empty(
                    chart_id="hive.observation",
                    scope=("x",),
                    ridge=1e-5,
                    observation_norm_bound=64.0,
                    prior_mass=1e-3,
                ),
            )
            source = SourceInput(
                source_id="hive-source-a",
                content=b'{"x":7}',
                media_type="application/json",
                codec="utf-8",
                observed_timestamp="t0",
                scope="hive-test",
                claim_category="observation",
                fidelity="direct",
            )
            observed = owner_a.admit_observation(
                operation_id="hive:observe:a",
                source=source,
                values={"x": 7.0},
                context={"task": "identity"},
            )
            event_id = observed["event"]["event_id"]
            program = FieldProgram(
                program_id=program_id,
                version=1,
                roles=("x",),
                steps=(PrimitiveStep("identity", "x_out", ("x",)),),
                outputs=("x_out",),
                support_event_ids=(event_id,),
                prefix_code_bits=1,
                status="promoted",
            )
            owner_a_receipt = owner_a.configure_program(
                "hive:configure:a",
                program,
            )
            candidate = ExperienceCandidate(
                kind="field-program",
                object=program.as_dict(),
                operation_plan=(
                    {
                        "operation": "configure-program",
                        "program": program.as_dict(),
                    },
                ),
                guards=(),
                dependencies=(),
            )
            experience = capsule_from_owner_transition(
                owner_a,
                {
                    "receipt": owner_a_receipt.as_dict(),
                    "source": observed["source"],
                    "event": observed["event"],
                },
                hive_id="hive-owner-test",
                instance_id="instance-a",
                role="scout",
                field_profile_sha256=profile,
                common_generation=0,
                task_id="identity",
                context={"domain": "owner-test"},
                action={"operation": "configure-program"},
                prediction={"output": 7},
                outcome={"output": 7},
                candidate=candidate,
                evidence=ExperienceEvidence(
                    support_event_ids=(event_id,),
                    assessment_ids=(),
                    held_out_results=({"output": 7},),
                    counterexamples=(),
                    derivation_roots=(),
                ),
            )
            independent = owner_b.configure_program(
                "hive:configure:b",
                program,
            )
            bundle = build_knowledge_bundle(
                (experience,),
                leader_instance_id="instance-a",
                authority_grant_sha256=digest("hive-authority"),
                predecessor_common_generation=0,
                reviews=(
                    Review(
                        reviewer_instance_id="instance-b",
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(independent.state_sha256),),
                    ),
                ),
            )

            source_owner_before = owner_b.state.state_sha256
            source_owner_replay = apply_bundle_to_owner(
                owner_b,
                bundle,
                recipient_instance_id="instance-b",
                field_profile_sha256=profile,
                current_common_generation=0,
            )
            assert source_owner_replay.status == "replayed"
            assert owner_b.state.state_sha256 == source_owner_before

            before = owner_c.state.state_sha256
            adopted = apply_bundle_to_owner(
                owner_c,
                bundle,
                recipient_instance_id="instance-c",
                field_profile_sha256=profile,
                current_common_generation=0,
                behavioral_delta={"program_admitted": True},
            )

            assert adopted.status == "accepted"
            assert adopted.field_effect_confirmed is False
            assert adopted.predecessor_state_sha256 == before
            assert adopted.successor_state_sha256 == owner_c.state.state_sha256
            assert adopted.successor_state_sha256 != before
            assert owner_c.state.program(program_id).status == "promoted"

            wrong_profile_before = owner_c.state.state_sha256
            wrong_profile = apply_bundle_to_owner(
                owner_c,
                bundle,
                recipient_instance_id="instance-c",
                field_profile_sha256=digest("wrong-profile"),
                current_common_generation=0,
            )
            assert wrong_profile.status == "incompatible"
            assert owner_c.state.state_sha256 == wrong_profile_before

            duplicate_before = owner_c.state.state_sha256
            duplicate = apply_bundle_to_owner(
                owner_c,
                bundle,
                recipient_instance_id="instance-c",
                field_profile_sha256=profile,
                current_common_generation=0,
            )
            assert duplicate.status == "replayed"
            assert owner_c.state.state_sha256 == duplicate_before
        finally:
            owner_a.close()
            owner_b.close()
            owner_c.close()


def test_multi_program_preflight_rejects_late_invalid_entry_without_mutation() -> None:
    profile = digest("field-profile")
    program = FieldProgram(
        program_id="preflight.program",
        version=1,
        roles=("x",),
        steps=(PrimitiveStep("identity", "x_out", ("x",)),),
        outputs=("x_out",),
        status="promoted",
    )
    source = capsule()
    candidate = replace(
        source.candidate,
        object=program.as_dict(),
        operation_plan=(
            {
                "operation": "promote-programs",
                "entries": (
                    {
                        "operation": "configure-program",
                        "program": program.as_dict(),
                    },
                    {
                        "operation": "configure-program",
                        "program": {"program_id": "malformed"},
                    },
                ),
            },
        ),
    )
    bundle = build_knowledge_bundle(
        (replace(source, candidate=candidate),),
        leader_instance_id="leader",
        authority_grant_sha256=digest("preflight-authority"),
        predecessor_common_generation=0,
        reviews=reviews(),
    )
    with TemporaryDirectory() as directory:
        owner = FieldIntelligenceOwner(__import__("pathlib").Path(directory))
        try:
            before = owner.state.state_sha256
            with pytest.raises(HiveProtocolError, match="program"):
                apply_bundle_to_owner(
                    owner,
                    bundle,
                    recipient_instance_id="instance-c",
                    field_profile_sha256=profile,
                    current_common_generation=0,
                )
            assert owner.state.state_sha256 == before
            assert owner.evidence.event_count == 0
        finally:
            owner.close()


def test_multi_program_runtime_failure_restores_durable_owner() -> None:
    profile = digest("field-profile")
    program_a = FieldProgram(
        program_id="transaction.a",
        version=1,
        roles=("x",),
        steps=(PrimitiveStep("identity", "a_out", ("x",)),),
        outputs=("a_out",),
        status="promoted",
    )
    program_b = FieldProgram(
        program_id="transaction.b",
        version=1,
        roles=("x",),
        steps=(PrimitiveStep("identity", "b_out", ("x",)),),
        outputs=("b_out",),
        status="promoted",
    )
    source = capsule()
    candidate = replace(
        source.candidate,
        object=program_a.as_dict(),
        operation_plan=(
            {
                "operation": "promote-programs",
                "entries": (
                    {"operation": "configure-program", "program": program_a.as_dict()},
                    {"operation": "configure-program", "program": program_b.as_dict()},
                ),
            },
        ),
    )
    bundle = build_knowledge_bundle(
        (replace(source, candidate=candidate),),
        leader_instance_id="leader",
        authority_grant_sha256=digest("transaction-authority"),
        predecessor_common_generation=0,
        reviews=reviews(),
    )
    with TemporaryDirectory() as directory:
        root = __import__("pathlib").Path(directory)
        owner = FieldIntelligenceOwner(root)
        original_configure = owner.configure_program
        before_state = owner.state.state_sha256
        before_manifest = owner.checkpoints.current_manifest_sha256

        def fail_on_second(operation_id: str, program: FieldProgram) -> Any:
            if program.program_id == program_b.program_id:
                raise RuntimeError("synthetic second-capability failure")
            return original_configure(operation_id, program)

        owner.configure_program = fail_on_second
        try:
            with pytest.raises(RuntimeError, match="second-capability"):
                apply_bundle_to_owner(
                    owner,
                    bundle,
                    recipient_instance_id="instance-c",
                    field_profile_sha256=profile,
                    current_common_generation=0,
                )
            assert owner.state.state_sha256 == before_state
            assert owner.checkpoints.current_manifest_sha256 == before_manifest
            assert owner.evidence.event_count == 0
            assert all(
                row.program_id not in {"transaction.a", "transaction.b"}
                for row in owner.state.programs
            )
        finally:
            owner.close()

        restored = FieldIntelligenceOwner(root)
        try:
            assert restored.state.state_sha256 == before_state
            assert restored.checkpoints.current_manifest_sha256 == before_manifest
            assert restored.evidence.event_count == 0
        finally:
            restored.close()


def test_genuinely_learned_program_transfers_between_owners() -> None:
    profile = digest("learned-owner-profile")
    with TemporaryDirectory() as directory:
        root = __import__("pathlib").Path(directory)
        owner_a = FieldIntelligenceOwner(root / "a")
        owner_b = FieldIntelligenceOwner(root / "b")
        owner_c = FieldIntelligenceOwner(root / "c")
        try:
            (
                program_payload,
                promotion_receipt,
                last_admitted,
                support_event_ids,
                assessment_ids,
                support_witnesses,
                assessment_witnesses,
            ) = learn_relative_program(owner_a)
            assert program_payload["status"] == "promoted"
            assert promotion_receipt["operation_id"] == "hive:learn:promote"

            program = FieldProgram.from_dict(program_payload)
            assert program.execute({"source": 3.0, "destination": 8.0}) == {
                "displacement": 5.0
            }
            candidate_payload = dict(program_payload)
            candidate_payload["status"] = "candidate"
            candidate_payload["version"] = 1
            candidate_payload["assessments"] = []
            variable_specs = [
                VariableSpec(
                    "bias",
                    kind="constant",
                    constant=1.0,
                    lower=1.0,
                    upper=1.0,
                ).as_dict(),
                VariableSpec("source", unit="m", lower=-20.0, upper=20.0).as_dict(),
                VariableSpec(
                    "destination",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
                VariableSpec(
                    "displacement",
                    unit="m",
                    lower=-40.0,
                    upper=40.0,
                ).as_dict(),
                VariableSpec("left_score", lower=-40.0, upper=40.0).as_dict(),
                VariableSpec("right_score", lower=-40.0, upper=40.0).as_dict(),
                VariableSpec(
                    "destination_value",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
                VariableSpec(
                    "source_value",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
                VariableSpec(
                    "source_scaled",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
                VariableSpec(
                    "destination_scaled",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
                VariableSpec(
                    "source_drift",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ).as_dict(),
            ]
            chart_specs = [
                {
                    "chart_id": "geometry.relative-position",
                    "scope": ["bias", "source", "destination", "displacement"],
                    "ridge": 1e-5,
                    "observation_norm_bound": 64.0,
                    "prior_mass": 1e-3,
                },
                {
                    "chart_id": "policy.direction",
                    "scope": ["bias", "displacement", "left_score", "right_score"],
                    "ridge": 1e-5,
                    "observation_norm_bound": 96.0,
                    "prior_mass": 1e-3,
                },
            ]
            held_out_witness = {
                "bindings": {"destination": 8.0, "source": 3.0},
                "context": {"domain": "line", "quality": "held-out"},
                "derivation_roots": [],
                "event_kind": "observation",
                "epistemic_type": "observed",
                "loss_scale": 10.0,
                "outcome": {"displacement": 5.0},
                "source": dict(
                    _source(
                        "episode:hive:learn:heldout",
                        {"destination": 8.0, "source": 3.0},
                        sequence=99,
                    ).as_dict()
                ),
                "values": {
                    "bias": 1.0,
                    "destination": 8.0,
                    "displacement": 5.0,
                    "left_score": -5.0,
                    "right_score": 5.0,
                    "source": 3.0,
                },
            }
            (
                source_role_payload,
                source_role_receipt,
                source_role_support,
                source_role_assessments,
                source_role_heldout,
            ) = learn_role_identity_program(
                owner_a,
                input_role="source",
                output_role="source_value",
                prefix="language-source",
                heldout_value=12.0,
            )
            source_role_program = owner_a.state.program(
                source_role_payload["program_id"]
            )
            (
                destination_role_payload,
                destination_role_receipt,
                destination_role_support,
                destination_role_assessments,
                destination_role_heldout,
            ) = learn_role_identity_program(
                owner_a,
                input_role="destination",
                output_role="destination_value",
                prefix="language-destination",
                heldout_value=13.0,
            )
            destination_role_program = owner_a.state.program(
                destination_role_payload["program_id"]
            )
            owner_a.configure_variable(
                "hive:learn:language:near:source-variable",
                VariableSpec("source_scaled", unit="m", lower=-20.0, upper=20.0),
            )
            distractor = FieldProgram(
                program_id="language.source.scaled",
                version=1,
                roles=("source",),
                steps=(
                    PrimitiveStep(
                        "convert",
                        "source_scaled",
                        ("source",),
                        literal=1.01,
                    ),
                ),
                outputs=("source_scaled",),
                support_event_ids=source_role_program.support_event_ids,
                prefix_code_bits=source_role_program.prefix_code_bits,
                status="promoted",
            )
            owner_a.configure_program(
                "hive:learn:language:near:source-configure",
                distractor,
            )
            owner_a.configure_variable(
                "hive:learn:language:near:destination-variable",
                VariableSpec(
                    "destination_scaled",
                    unit="m",
                    lower=-20.0,
                    upper=20.0,
                ),
            )
            swapped = FieldProgram(
                program_id="language.destination.scaled",
                version=1,
                roles=("destination",),
                steps=(
                    PrimitiveStep(
                        "convert",
                        "destination_scaled",
                        ("destination",),
                        literal=0.99,
                    ),
                ),
                outputs=("destination_scaled",),
                support_event_ids=destination_role_program.support_event_ids,
                prefix_code_bits=destination_role_program.prefix_code_bits,
                status="promoted",
            )
            owner_a.configure_program(
                "hive:learn:language:near:destination-configure",
                swapped,
            )
            owner_a.configure_variable(
                "hive:learn:language:near:drift-variable",
                VariableSpec("source_drift", unit="m", lower=-20.0, upper=20.0),
            )
            nonlinear = FieldProgram(
                program_id="language.source.drift",
                version=1,
                roles=("source",),
                steps=(
                    PrimitiveStep(
                        "convert",
                        "source_drift",
                        ("source",),
                        literal=1.005,
                    ),
                ),
                outputs=("source_drift",),
                support_event_ids=source_role_program.support_event_ids,
                prefix_code_bits=source_role_program.prefix_code_bits + 1,
                status="promoted",
            )
            owner_a.configure_program(
                "hive:learn:language:near:drift-configure",
                nonlinear,
            )
            (
                composite_payload,
                composite_receipt,
                composite_support,
                composite_assessments,
                composite_heldout,
            ) = compose_language_program(
                owner_a,
                frontier_program_ids=(
                    destination_role_program.program_id,
                    source_role_program.program_id,
                    distractor.program_id,
                    swapped.program_id,
                    nonlinear.program_id,
                    program.program_id,
                ),
                support_witnesses=source_role_support + destination_role_support,
            )
            composite_program = owner_a.state.program(
                composite_payload["program_id"]
            )
            promotion_entry = {
                "operation": "promote-program",
                "program": candidate_payload,
                "support_witnesses": support_witnesses,
                "assessment_witnesses": assessment_witnesses,
                "variable_specs": variable_specs,
                "chart_specs": chart_specs,
                "held_out_witness": held_out_witness,
                "minimum_assessments": 3,
                "maximum_average_loss": 1e-12,
                "bit_penalty": 1e-6,
            }
            multi_operation = {
                "operation": "promote-programs",
                "entries": (
                    promotion_entry,
                    {
                        "operation": "promote-program",
                        "program": source_role_payload,
                        "support_witnesses": source_role_support,
                        "assessment_witnesses": source_role_assessments,
                        "variable_specs": variable_specs,
                        "chart_specs": chart_specs,
                        "held_out_witness": source_role_heldout,
                        "minimum_assessments": 3,
                        "maximum_average_loss": 1e-12,
                        "bit_penalty": 1e-6,
                    },
                    {
                        "operation": "promote-program",
                        "program": destination_role_payload,
                        "support_witnesses": destination_role_support,
                        "assessment_witnesses": destination_role_assessments,
                        "variable_specs": variable_specs,
                        "chart_specs": chart_specs,
                        "held_out_witness": destination_role_heldout,
                        "minimum_assessments": 3,
                        "maximum_average_loss": 1e-12,
                        "bit_penalty": 1e-6,
                    },
                    {
                        "operation": "promote-program",
                        "program": composite_payload,
                        "support_witnesses": composite_support,
                        "assessment_witnesses": composite_assessments,
                        "variable_specs": variable_specs,
                        "chart_specs": chart_specs,
                        "held_out_witness": composite_heldout,
                        "minimum_assessments": 3,
                        "maximum_average_loss": 1e-12,
                        "bit_penalty": 1e-6,
                    },
                ),
            }
            candidate = ExperienceCandidate(
                kind="field-program",
                object=program_payload,
                operation_plan=(multi_operation,),
                guards=(),
                dependencies=(),
            )
            experience = capsule_from_owner_transition(
                owner_a,
                {
                    "receipt": composite_receipt,
                    "source": last_admitted["source"],
                    "event": last_admitted["event"],
                },
                hive_id="hive-learned-program",
                instance_id="instance-a",
                role="field-apprentice",
                field_profile_sha256=profile,
                common_generation=0,
                task_id="relative-position",
                context={"domain": "owner-learning"},
                action={"operation": "promote-program"},
                prediction={"program_id": program.program_id},
                outcome={"program_status": "promoted"},
                candidate=candidate,
                evidence=ExperienceEvidence(
                    support_event_ids=support_event_ids,
                    assessment_ids=assessment_ids,
                    held_out_results=(
                        {"source": 3.0, "destination": 8.0, "displacement": 5.0},
                    ),
                    counterexamples=(),
                    derivation_roots=(),
                ),
            )
            assert experience.origin.predecessor_state_sha256 != experience.origin.successor_state_sha256

            independent = owner_b.configure_program(
                "hive:learned-program:review",
                program,
            )
            bundle = build_knowledge_bundle(
                (experience,),
                leader_instance_id="instance-a",
                authority_grant_sha256=digest("learned-program-authority"),
                predecessor_common_generation=0,
                reviews=(
                    Review(
                        reviewer_instance_id="instance-b",
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(independent.state_sha256),),
                    ),
                ),
            )

            tampered_operations = []
            for operation in experience.candidate.operation_plan:
                operation_copy = dict(operation)
                if operation_copy.get("operation") == "promote-programs":
                    entries = []
                    for raw_entry in operation_copy["entries"]:
                        entry = dict(raw_entry)
                        if entry["program"]["program_id"] == source_role_program.program_id:
                            witnesses = list(entry["assessment_witnesses"])
                            witnesses[0] = dict(witnesses[0])
                            witnesses[0]["resolution_floor"] = 1e-15
                            witnesses[0]["resolution_status"] = "unresolved"
                            entry["assessment_witnesses"] = tuple(witnesses)
                        entries.append(entry)
                    operation_copy["entries"] = tuple(entries)
                tampered_operations.append(operation_copy)
            tampered_candidate = replace(
                experience.candidate,
                operation_plan=tuple(tampered_operations),
            )
            tampered_experience = replace(
                experience,
                candidate=tampered_candidate,
            )
            tampered_bundle = build_knowledge_bundle(
                (tampered_experience,),
                leader_instance_id="instance-a",
                authority_grant_sha256=digest("learned-program-authority"),
                predecessor_common_generation=0,
                reviews=(
                    Review(
                        reviewer_instance_id="instance-b",
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(independent.state_sha256),),
                    ),
                ),
            )
            unresolved_before = owner_c.state.state_sha256
            with pytest.raises(HiveProtocolError, match="unresolved"):
                apply_bundle_to_owner(
                    owner_c,
                    tampered_bundle,
                    recipient_instance_id="instance-c",
                    field_profile_sha256=profile,
                    current_common_generation=0,
                )
            assert owner_c.state.state_sha256 == unresolved_before
            omitted_operations = []
            for operation in tampered_operations:
                operation_copy = dict(operation)
                if operation_copy.get("operation") == "promote-programs":
                    entries = []
                    for raw_entry in operation_copy["entries"]:
                        entry = dict(raw_entry)
                        if entry["program"]["program_id"] == source_role_program.program_id:
                            witnesses = list(entry["assessment_witnesses"])
                            witness = dict(witnesses[0])
                            witness.pop("resolution_floor", None)
                            witness.pop("resolution_status", None)
                            witnesses[0] = witness
                            entry["assessment_witnesses"] = tuple(witnesses)
                        entries.append(entry)
                    operation_copy["entries"] = tuple(entries)
                omitted_operations.append(operation_copy)
            omitted_experience = replace(
                experience,
                candidate=replace(
                    experience.candidate,
                    operation_plan=tuple(omitted_operations),
                ),
            )
            omitted_bundle = build_knowledge_bundle(
                (omitted_experience,),
                leader_instance_id="instance-a",
                authority_grant_sha256=digest("learned-program-authority"),
                predecessor_common_generation=0,
                reviews=(
                    Review(
                        reviewer_instance_id="instance-b",
                        review_type="independent-reproduction",
                        result="supports",
                        evidence_ids=(digest(independent.state_sha256),),
                    ),
                ),
            )
            omitted_before = owner_c.state.state_sha256
            with pytest.raises(
                HiveProtocolError,
                match="replay witnesses are invalid",
            ):
                apply_bundle_to_owner(
                    owner_c,
                    omitted_bundle,
                    recipient_instance_id="instance-c",
                    field_profile_sha256=profile,
                    current_common_generation=0,
                )
            assert owner_c.state.state_sha256 == omitted_before

            before = owner_c.state.state_sha256
            adopted = apply_bundle_to_owner(
                owner_c,
                bundle,
                recipient_instance_id="instance-c",
                field_profile_sha256=profile,
                current_common_generation=0,
                behavioral_delta={"program_learned_elsewhere": True},
            )

            assert adopted.status == "accepted"
            assert adopted.predecessor_state_sha256 == before
            assert owner_c.state.program(program.program_id).status == "promoted"
            assert owner_c.state.program(source_role_program.program_id).status == "promoted"
            assert owner_c.state.program(source_role_program.program_id).execute(
                {"source": 12.0}
            ) == {"source_value": 12.0}
            assert owner_c.state.program(destination_role_program.program_id).status == "promoted"
            assert owner_c.state.program(destination_role_program.program_id).execute(
                {"destination": 13.0}
            ) == {"destination_value": 13.0}
            assert owner_c.state.program(composite_program.program_id).status == "promoted"
            assert owner_c.state.program(composite_program.program_id).execute(
                {"destination": 9.0, "source": 4.0}
            ) == {"source_value": 4.0, "destination_value": 9.0}
            assert adopted.successor_state_sha256 == owner_c.state.state_sha256
            assert len(owner_c.state.program(program.program_id).assessments) == 4
            assert len(adopted.post_adoption_observation_ids) == 4
            assert len(adopted.applied_object_ids) == 4
            assert len(adopted.behavioral_delta["capabilities"]) == 4
            assert all(
                item["behavioral_delta"]["held_out"]["normalized_loss"] == 0.0
                for item in adopted.behavioral_delta["capabilities"]
            )
            for program_id in (
                source_role_program.program_id,
                destination_role_program.program_id,
                composite_program.program_id,
            ):
                assessments = owner_c.state.program(program_id).assessments
                assert all(
                    assessment.resolution_status == "resolved"
                    and assessment.resolution_floor >= 0.0
                    for assessment in assessments
                )
            assert all(
                item["behavioral_delta"]["held_out"]["resolution_status"]
                == "resolved"
                for item in adopted.behavioral_delta["capabilities"]
            )
            assert owner_c.evidence.event_count == 26
            duplicate_before = owner_c.state.state_sha256
            duplicate = apply_bundle_to_owner(
                owner_c,
                bundle,
                recipient_instance_id="instance-c",
                field_profile_sha256=profile,
                current_common_generation=0,
            )
            assert duplicate.status == "replayed"
            assert owner_c.state.state_sha256 == duplicate_before
            assert owner_c.evidence.event_count == 26
        finally:
            owner_a.close()
            owner_b.close()
            owner_c.close()


def test_near_miss_margin_and_sample_sweep() -> None:
    sample_values = (1.0, 2.0, 4.0)
    margins = (1e-14, 1e-13, 1e-12, 1e-11, 1e-10, 0.001, 0.01, 0.05)
    for margin in margins:
        for sample_count in (1, 2, 3):
            scenario = f"margin-{margin}-samples-{sample_count}".replace(".", "_")
            with TemporaryDirectory() as directory:
                owner = FieldIntelligenceOwner(
                    __import__("pathlib").Path(directory)
                )
                try:
                    for index, variable_id in enumerate(
                        (
                            "source",
                            "destination",
                            "source_value",
                            "destination_value",
                            "source_scaled",
                        )
                    ):
                        owner.configure_variable(
                            f"sweep:{scenario}:variable:{index}",
                            VariableSpec(
                                variable_id,
                                unit="m",
                                lower=-100.0,
                                upper=100.0,
                            ),
                        )
                    owner.configure_chart(
                        f"sweep:{scenario}:chart",
                        RelationChart.empty(
                            chart_id=f"sweep.{scenario}.chart",
                            scope=("source", "destination"),
                            ridge=1e-5,
                            observation_norm_bound=100.0,
                            prior_mass=1e-3,
                        ),
                    )
                    source_program = FieldProgram(
                        program_id=f"sweep.{scenario}.source",
                        version=1,
                        roles=("source",),
                        steps=(
                            PrimitiveStep("identity", "source_value", ("source",)),
                        ),
                        outputs=("source_value",),
                        prefix_code_bits=4,
                        status="promoted",
                    )
                    destination_program = FieldProgram(
                        program_id=f"sweep.{scenario}.destination",
                        version=1,
                        roles=("destination",),
                        steps=(
                            PrimitiveStep(
                                "identity",
                                "destination_value",
                                ("destination",),
                            ),
                        ),
                        outputs=("destination_value",),
                        prefix_code_bits=4,
                        status="promoted",
                    )
                    near_program = FieldProgram(
                        program_id=f"sweep.{scenario}.near",
                        version=1,
                        roles=("source",),
                        steps=(
                            PrimitiveStep(
                                "convert",
                                "source_scaled",
                                ("source",),
                                literal=1.0 + margin,
                            ),
                        ),
                        outputs=("source_scaled",),
                        prefix_code_bits=5,
                        status="promoted",
                    )
                    for index, program in enumerate(
                        (source_program, destination_program, near_program)
                    ):
                        owner.configure_program(
                            f"sweep:{scenario}:program:{index}",
                            program,
                        )
                    proposal = owner.propose_program_compositions(
                        operation_id=f"sweep:{scenario}:frontier",
                        problem_id=f"sweep.{scenario}",
                        program_ids=(
                            destination_program.program_id,
                            source_program.program_id,
                            near_program.program_id,
                        ),
                        minimum_components=2,
                        maximum_components=2,
                        maximum_candidates=2,
                        maximum_steps=2,
                        maximum_prefix_code_bits=32,
                    )
                    candidate_ids = tuple(proposal["candidate_ids"])
                    assert len(candidate_ids) == 2
                    for candidate_id in candidate_ids:
                        candidate = owner.state.program(candidate_id)
                        for index, source in enumerate(sample_values[:sample_count]):
                            destination = source + 3.0
                            bindings = {
                                role: {
                                    "source": source,
                                    "destination": destination,
                                }[role]
                                for role in candidate.roles
                            }
                            begun = owner.begin_program_assessment(
                                operation_id=(
                                    f"sweep:{scenario}:begin:{candidate_id}:{index}"
                                ),
                                program_id=candidate_id,
                                bindings=bindings,
                            )
                            admitted = owner.admit_observation(
                                operation_id=(
                                    f"sweep:{scenario}:observation:"
                                    f"{candidate_id}:{index}"
                                ),
                                source=_source(
                                    f"episode:sweep:{scenario}:{candidate_id}:{index}",
                                    {
                                        "source": source,
                                        "destination": destination,
                                    },
                                    sequence=index + 1,
                                ),
                                values={
                                    "source": source,
                                    "destination": destination,
                                    "source_value": source,
                                    "destination_value": destination,
                                    "source_scaled": source,
                                },
                                context={"domain": "sweep", "quality": "controlled"},
                            )
                            event = admitted["event"]
                            outcome = {
                                name: event["values"][name]
                                for name in candidate.outputs
                            }
                            owner.resolve_program_assessment(
                                operation_id=(
                                    f"sweep:{scenario}:resolve:"
                                    f"{candidate_id}:{index}"
                                ),
                                program_id=candidate_id,
                                prediction_id=begun["prediction"]["prediction_id"],
                                outcome=outcome,
                                event_id=event["event_id"],
                                loss_scale=1.0,
                            )
                    exact = owner.state.program(candidate_ids[0])
                    near = owner.state.program(candidate_ids[1])
                    expected_near_loss = margin * sum(
                        abs(value) for value in sample_values[:sample_count]
                    ) / sample_count
                    assert math.isclose(exact.prequential_loss, 0.0, abs_tol=1e-12)
                    assert math.isclose(
                        near.prequential_loss / sample_count,
                        expected_near_loss,
                        rel_tol=1e-12,
                        abs_tol=1e-12,
                    )
                    near_average_loss = near.prequential_loss / sample_count
                    if (
                        near_average_loss <= 1e-12
                        and all(
                            item.resolution_status == "resolved"
                            for item in near.assessments
                        )
                    ):
                        near_promoted = owner.promote_program(
                            operation_id=f"sweep:{scenario}:promote-near",
                            candidate_ids=(candidate_ids[1],),
                            minimum_assessments=sample_count,
                            maximum_average_loss=1e-12,
                            bit_penalty=1e-6,
                        )
                        assert (
                            near_promoted["program"]["program_id"]
                            == candidate_ids[1]
                        )
                        promoted = owner.promote_program(
                            operation_id=f"sweep:{scenario}:promote-exact",
                            candidate_ids=(candidate_ids[0],),
                            minimum_assessments=sample_count,
                            maximum_average_loss=1e-12,
                            bit_penalty=1e-6,
                        )
                    else:
                        with pytest.raises(FieldIntelligenceError):
                            owner.promote_program(
                                operation_id=f"sweep:{scenario}:reject-near",
                                candidate_ids=(candidate_ids[1],),
                                minimum_assessments=sample_count,
                                maximum_average_loss=1e-12,
                                bit_penalty=1e-6,
                            )
                        promoted = owner.promote_program(
                            operation_id=f"sweep:{scenario}:promote-exact",
                            candidate_ids=(candidate_ids[0],),
                            minimum_assessments=sample_count,
                            maximum_average_loss=1e-12,
                            bit_penalty=1e-6,
                        )
                    assert promoted["program"]["program_id"] == candidate_ids[0]
                finally:
                    owner.close()


def test_near_miss_threshold_cancellation_and_mutation_control() -> None:
    def measure(
        label: str,
        source: float,
        margin: float,
        loss_scale: float,
        declared_floor: float | None = None,
    ) -> tuple[float, str]:
        with TemporaryDirectory() as directory:
            owner = FieldIntelligenceOwner(
                __import__("pathlib").Path(directory)
            )
            try:
                for index, variable_id in enumerate(
                    (
                        "source",
                        "destination",
                        "source_value",
                        "destination_value",
                        "source_scaled",
                    )
                ):
                    owner.configure_variable(
                        f"control:{label}:variable:{index}",
                        VariableSpec(
                            variable_id,
                            unit="m",
                            lower=-1e18,
                            upper=1e18,
                        ),
                    )
                owner.configure_chart(
                    f"control:{label}:chart",
                    RelationChart.empty(
                        chart_id=f"control.{label}.chart",
                        scope=("source", "destination"),
                        ridge=1e-5,
                        observation_norm_bound=1e18,
                        prior_mass=1e-3,
                    ),
                )
                exact_source = FieldProgram(
                    program_id=f"control.{label}.source",
                    version=1,
                    roles=("source",),
                    steps=(
                        PrimitiveStep("identity", "source_value", ("source",)),
                    ),
                    outputs=("source_value",),
                    prefix_code_bits=4,
                    status="promoted",
                )
                exact_destination = FieldProgram(
                    program_id=f"control.{label}.destination",
                    version=1,
                    roles=("destination",),
                    steps=(
                        PrimitiveStep(
                            "identity",
                            "destination_value",
                            ("destination",),
                        ),
                    ),
                    outputs=("destination_value",),
                    prefix_code_bits=4,
                    status="promoted",
                )
                near = FieldProgram(
                    program_id=f"control.{label}.near",
                    version=1,
                    roles=("source",),
                    steps=(
                        PrimitiveStep(
                            "convert",
                            "source_scaled",
                            ("source",),
                            literal=1.0 + margin,
                        ),
                    ),
                    outputs=("source_scaled",),
                    prefix_code_bits=5,
                    status="promoted",
                )
                for index, program in enumerate(
                    (exact_source, exact_destination, near)
                ):
                    owner.configure_program(
                        f"control:{label}:program:{index}",
                        program,
                    )
                proposal = owner.propose_program_compositions(
                    operation_id=f"control:{label}:frontier",
                    problem_id=f"control.{label}",
                    program_ids=(
                        exact_destination.program_id,
                        exact_source.program_id,
                        near.program_id,
                    ),
                    minimum_components=2,
                    maximum_components=2,
                    maximum_candidates=2,
                    maximum_steps=2,
                    maximum_prefix_code_bits=32,
                )
                candidate_ids = tuple(proposal["candidate_ids"])
                for candidate_id in candidate_ids:
                    candidate = owner.state.program(candidate_id)
                    bindings = {
                        role: {
                            "source": source,
                            "destination": source + 3.0,
                        }[role]
                        for role in candidate.roles
                    }
                    begun = owner.begin_program_assessment(
                        operation_id=f"control:{label}:begin:{candidate_id}",
                        program_id=candidate_id,
                        bindings=bindings,
                    )
                    values = {
                        "source": source,
                        "destination": source + 3.0,
                        "source_value": source,
                        "destination_value": source + 3.0,
                        "source_scaled": source,
                    }
                    admitted = owner.admit_observation(
                        operation_id=f"control:{label}:observation:{candidate_id}",
                        source=_source(
                            f"episode:control:{label}",
                            {
                                "source": source,
                                "destination": source + 3.0,
                            },
                            sequence=1,
                        ),
                        values=values,
                        context={"domain": "threshold-control", "quality": "controlled"},
                    )
                    event = admitted["event"]
                    outcome = {
                        name: event["values"][name]
                        for name in candidate.outputs
                    }
                    owner.resolve_program_assessment(
                        operation_id=f"control:{label}:resolve:{candidate_id}",
                        program_id=candidate_id,
                        prediction_id=begun["prediction"]["prediction_id"],
                        outcome=outcome,
                        event_id=event["event_id"],
                        loss_scale=loss_scale,
                        resolution_floor=declared_floor,
                    )
                near_assessment = owner.state.program(candidate_ids[1]).assessments[0]
                if declared_floor is not None:
                    if near_assessment.resolution_status == "unresolved":
                        with pytest.raises(FieldIntelligenceError):
                            owner.promote_program(
                                operation_id=f"control:{label}:reject-unresolved",
                                candidate_ids=(candidate_ids[1],),
                                minimum_assessments=1,
                                maximum_average_loss=1.0,
                                bit_penalty=1e-6,
                            )
                    else:
                        promoted = owner.promote_program(
                            operation_id=f"control:{label}:accept-resolved",
                            candidate_ids=(candidate_ids[1],),
                            minimum_assessments=1,
                            maximum_average_loss=1.0,
                            bit_penalty=1e-6,
                        )
                        assert (
                            promoted["program"]["program_id"]
                            == candidate_ids[1]
                        )
                return (
                    near_assessment.normalized_loss,
                    near_assessment.resolution_status,
                )
            finally:
                owner.close()

    unit_loss, _ = measure("unit", 1.0, 1e-12, 1.0)
    scaled_loss, _ = measure("scaled", 1e4, 1e-12, 1e4)
    cancellation_loss, cancellation_status = measure(
        "cancellation",
        1e3,
        1e-16,
        1.0,
        declared_floor=1e-15,
    )
    mutated_loss, mutated_status = measure(
        "mutation",
        1e3,
        1e-12,
        1.0,
        declared_floor=1e-15,
    )

    assert math.isclose(unit_loss, 1e-12, rel_tol=1e-3, abs_tol=1e-24)
    assert math.isclose(scaled_loss, 1e-12, rel_tol=1e-3, abs_tol=1e-24)
    assert cancellation_loss == 0.0
    assert cancellation_status == "unresolved"
    assert mutated_status == "resolved"
    assert mutated_loss > cancellation_loss
