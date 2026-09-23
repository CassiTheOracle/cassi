"""Focused owner-path coverage for cognition capability provenance and language."""
from __future__ import annotations

import hashlib

from typing import Any, Mapping
import pytest
from cassi_field_open_vocab import episode_source_payload
from cassi_field_atlas import canonical_json_bytes
from cassi_field_cognition import regional_sustained_episode_state
from cassi_field_owner import AuthorityGrant, SourceInput
from cassi_field_cognition import (
    regional_construction_learning_state,
    regional_language_state,
    semantic_cognition_state,
)
from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA


def call(owner: FieldIntelligenceOwner, request_id: str, action: str, **arguments: Any) -> Mapping[str, Any]:
    return FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": request_id,
            "operation": "computer",
            "params": {
                "operation_id": request_id,
                "computer_id": "main",
                "action": action,
                "arguments": arguments,
            },
        }
    )["result"]

def event(label: str) -> str:
    return hashlib.sha256(label.encode("utf-8")).hexdigest()


def development_request(episode_id: str, *, numeric_work: list[int] | None) -> dict[str, Any]:
    information: dict[str, Any] = {"task_family": "arithmetic"}
    if numeric_work is not None:
        information["numeric_work"] = numeric_work
    return {
        "operation": "start-development",
        "operation_id": f"start-{episode_id}",
        "episode_id": episode_id,
        "capability_target": {"parameter": "arithmetic-total"},
        "diagnosis": "method-selection",
        "remit": {"purpose": "improve-current-reasoning"},
        "available_information": information,
        "capabilities": {
            "evidence_reads": False,
            "model_calls": False,
            "sandbox": False,
        },
        "write_classes": [],
        "allocation": {
            "evidence_reads": 0,
            "model_calls": 0,
            "storage_words": 128,
            "work": 32,
        },
        "assessment": {"predicted": 42, "actual": 42},
        "stopping_condition": {"max_attempts": 1},
    }


def finish_development(
    owner: FieldIntelligenceOwner, episode_id: str
) -> Mapping[str, Any]:
    started = owner.state.computers[0].inspect()["consumed_result"]
    call(owner, f"run-{episode_id}", "call", **started["invocation"], steps=128)
    call(
        owner,
        f"finish-{episode_id}",
        "invoke",
        arguments={
            "operation": "finish-development",
            "operation_id": f"finish-{episode_id}",
            "episode_id": episode_id,
        },
        steps=128,
    )
    return owner.state.computers[0].inspect()["consumed_result"]


def test_observation_returns_its_admitted_obligation(tmp_path) -> None:
    with FieldIntelligenceOwner(tmp_path / "obligation") as owner:
        call(owner, "configure-obligation", "configure")
        call(
            owner,
            "observe-obligation",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "observe-obligation",
                "delivery_id": "observe-obligation",
                "event_id": "observe-obligation",
                "observations": [
                    {
                        "binding_id": "review-subject",
                        "subject": "research",
                        "attribute": "review_due",
                        "value": True,
                    }
                ],
                "obligations": [
                    {
                        "obligation_id": "review-duty",
                        "purpose": "answer-affected-people",
                        "priority": 1.0,
                    }
                ],
            },
            steps=128,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["obligations"] == [
            {"content_version": 1, "id": "review-duty", "kind": "Obligation"}
        ]


def test_executed_development_outcome_is_observed_and_reusable(tmp_path) -> None:
    with FieldIntelligenceOwner(tmp_path / "executed") as owner:
        call(owner, "configure", "configure")
        call(
            owner,
            "prime-executed",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "prime-executed",
                "delivery_id": "prime-executed",
                "event_id": "prime-executed",
                "observations": [
                    {
                        "binding_id": "seed",
                        "subject": "seed",
                        "attribute": "value",
                        "value": 1,
                    }
                ],
            },
            steps=128,
        )
        call(
            owner,
            "start-executed",
            "invoke",
            arguments=development_request("executed", numeric_work=[10, 32]),
            steps=128,
        )
        finished = finish_development(owner, "executed")
        assert finished["provenance"] == "executed"
        assert finished["observed_outcome"] == 42.0
        assert finished["verified_improvement"] is True
        assert finished["assessment"]["kind"] == "Assessment"

        call(
            owner,
            "reuse-executed",
            "invoke",
            arguments={
                "operation": "reuse-development-method",
                "operation_id": "reuse-executed",
                "task_family": "arithmetic",
            },
            steps=128,
        )
        reused = owner.state.computers[0].inspect()["consumed_result"]
        assert reused["status"] == "supported"
        assert reused["reused"] is True
        assert reused["applicability"] == {"task_family": "arithmetic"}
        assert reused["method"]["id"] == "development-method:executed"

@pytest.mark.parametrize("explicit_work", [None, {"kind": "none"}])
def test_caller_assessment_without_work_is_not_verified_observation(
    tmp_path, explicit_work
) -> None:
    with FieldIntelligenceOwner(tmp_path / "caller") as owner:
        call(owner, "configure", "configure")
        call(
            owner,
            "prime-caller",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "prime-caller",
                "delivery_id": "prime-caller",
                "event_id": "prime-caller",
                "observations": [
                    {
                        "binding_id": "seed",
                        "subject": "seed",
                        "attribute": "value",
                        "value": 1,
                    }
                ],
            },
            steps=128,
        )
        call(
            owner,
            "start-caller",
            "invoke",
            arguments={
                **development_request("caller", numeric_work=None),
                "executed_work": explicit_work,
            },
            steps=128,
        )
        finished = finish_development(owner, "caller")
        assert finished["provenance"] == "caller-supplied"
        assert finished["observed_outcome"] is None
        assert finished["verified_improvement"] is False
        assert finished["assessment"]["kind"] == "Assessment"

def test_regenerated_explanation_binds_corrected_premise_revision(tmp_path) -> None:
    target = "calibration-valve-7"
    scope = "workshop:bay-17"
    with FieldIntelligenceOwner(tmp_path / "episode") as owner:
        source = SourceInput(
            source_id="episode-source",
            content=canonical_json_bytes({"instrument": "gauge"}),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="episode-time",
            scope=scope,
            claim_category="controlled-observation",
            fidelity="exact-record",
            labels=("test",),
        )
        archived = owner.archive_source(
            operation_id="archive-episode-source",
            source=source,
            context={},
            event_kind="episode-observation",
        )
        revision = archived["source"]["revision_id"]
        call(owner, "configure-episode", "configure")
        task = regional_sustained_episode_state(
            instrument_alias="north-gauge",
            location_alias="bay-seven",
            access_allowed=False,
            source_revision_id=revision,
            action_target=target,
            action_scope=scope,
            numeric_work=(2.0, 3.0),
        )
        call(
            owner,
            "submit-episode",
            "submit",
            kernel="cognition.field",
            state=task,
            steps=128,
        )
        correction = "b" * 64
        call(
            owner,
            "correct-episode",
            "invoke",
            arguments={
                "operation": "premise-change",
                "event_id": correction,
                "source_revision_id": revision,
                "access_allowed": True,
            },
            steps=128,
        )
        proposal = owner.state.computers[0].inspect()["task"]["continuation"][
            "proposal"
        ]
        grant = AuthorityGrant(
            grant_id="episode-grant",
            issuer="capability-test",
            generation=owner.authority_generation,
            operation="computer-effect",
            target=target,
            scope=scope,
        )
        call(
            owner,
            "authorize-episode",
            "authorized-invoke",
            arguments={
                "operation": "authorize-action",
                "proposal_id": proposal["proposal_id"],
            },
            grant=grant.as_dict(),
            target=target,
            scope=scope,
            steps=128,
        )
        call(
            owner,
            "dispatch-episode",
            "authorized-invoke",
            arguments={
                "operation": "dispatch-action",
                "proposal_id": proposal["proposal_id"],
                "adapter_id": "capability-test-adapter",
                "dispatch_id": "dispatch:capability-test",
                "idempotency": "guaranteed",
                "idempotency_key": "idempotency:capability-test",
            },
            grant=grant.as_dict(),
            target=target,
            scope=scope,
            steps=128,
        )
        call(
            owner,
            "acknowledge-episode",
            "invoke",
            arguments={
                "operation": "acknowledgment",
                "event_id": "c" * 64,
                "proposal_id": proposal["proposal_id"],
                "status": "succeeded",
            },
            steps=128,
        )
        call(owner, "render-episode", "advance", steps=128)
        explanation = owner.state.computers[0].inspect()["task"]["continuation"][
            "explanation"
        ]
        assert explanation["support_event_ids"] == [revision]
        assert explanation["premise_revision_ids"] == [correction]



def test_language_learns_negation_and_reordered_roles_through_owner(tmp_path) -> None:
    program = {
        "program_id": "located-meaning",
        "version": 1,
        "roles": ["item", "place"],
        "steps": [
            {"operation": "vector", "inputs": ["item", "place"], "output": "meaning"}
        ],
        "outputs": ["meaning"],
        "status": "promoted",
    }
    acquisition = (
        {
            "event_id": event("acquire-positive"),
            "roles": {"item": "red sensor", "place": "north cabinet"},
            "text": "the red sensor is in north cabinet",
        },
        {
            "event_id": event("acquire-negated"),
            "roles": {"item": "blue probe", "place": "south drawer"},
            "text": "the blue probe is not in south drawer",
        },
        {
            "event_id": event("acquire-reordered"),
            "roles": {"item": "amber meter", "place": "west locker"},
            "text": "in west locker is amber meter",
        },
    )
    validation = (
        {
            "event_id": event("validate-negated"),
            "roles": {"item": "green device", "place": "east bin"},
            "text": "the green device is not in east bin",
        },
        {
            "event_id": event("validate-reordered"),
            "roles": {"item": "silver gauge", "place": "rear shelf"},
            "text": "in rear shelf is silver gauge",
        },
    )
    with FieldIntelligenceOwner(tmp_path / "language") as owner:
        call(owner, "configure", "configure")
        learning = regional_construction_learning_state(
            acquisition,
            validation,
            construction_id="learned-location",
            semantic_program_id="located-meaning",
        )
        call(
            owner,
            "learn-language",
            "submit",
            kernel="cognition.field",
            state=learning,
            steps=256,
        )
        learned = owner.state.computers[0].inspect()["consumed_result"]
        assert learned["status"] == "learned"
        construction = learned["construction"]
        assert len(construction["pattern_variants"]) == 3
        assert any("not" in pattern for pattern in construction["pattern_variants"])
        assert any(
            pattern[:3] == ["in", "{place}", "is"]
            for pattern in construction["pattern_variants"]
        )
        construction_id = construction["construction_id"]

        interpreted_negation = regional_language_state(
            (construction,),
            mode="interpret",
            text="the green device is not in east bin",
            semantic_programs=(program,),
        )
        call(
            owner,
            "interpret-negation",
            "submit",
            kernel="cognition.field",
            state=interpreted_negation,
            steps=256,
        )
        negated = owner.state.computers[0].inspect()["consumed_result"]
        assert negated["status"] == "understood"
        assert negated["branches"][0]["bindings"] == {
            "item": "green device",
            "place": "east bin",
        }

        interpreted_reordered = regional_language_state(
            (construction,),
            mode="interpret",
            text="in rear shelf is silver gauge",
            semantic_programs=(program,),
        )
        call(
            owner,
            "interpret-reordered",
            "submit",
            kernel="cognition.field",
            state=interpreted_reordered,
            steps=256,
        )
        reordered = owner.state.computers[0].inspect()["consumed_result"]
        assert reordered["status"] == "understood"
        assert reordered["branches"][0]["bindings"] == {
            "item": "silver gauge",
            "place": "rear shelf",
        }

        expressed = regional_language_state(
            (construction,),
            mode="express",
            bindings={"item": "silver gauge", "place": "rear shelf"},
            semantic_program_id="located-meaning",
            semantic_programs=(program,),
        )
        call(
            owner,
            "express-reordered",
            "submit",
            kernel="cognition.field",
            state=expressed,
            steps=256,
        )
        expression = owner.state.computers[0].inspect()["consumed_result"]
        assert expression["status"] == "expressed"
        # Both acquired forms express the same positive meaning; a negated
        # render of a positive binding, or a dropped role, would be a defect.
        assert expression["text"] in {
            "in rear shelf is silver gauge",
            "the silver gauge is in rear shelf",
        }, expression["text"]

    with FieldIntelligenceOwner(tmp_path / "language") as owner:
        retained_task = owner.state.computers[0].inspect()["task"]
        retained_constructions = retained_task["source"]["constructions"]
        assert retained_constructions[0]["construction_id"] == construction_id

    with FieldIntelligenceOwner(tmp_path / "cold") as owner:
        call(owner, "configure", "configure")
        cold = regional_language_state(
            (),
            mode="interpret",
            text="the green device is not in east bin",
        )
        call(
            owner,
            "cold-language",
            "submit",
            kernel="cognition.field",
            state=cold,
            steps=64,
        )
        assert owner.state.computers[0].inspect()["consumed_result"]["status"] == (
            "representation-insufficient"
        )


def test_autonomous_learning_persists_selection_through_owner(tmp_path) -> None:
    from cassi_field_cognition import semantic_cognition_state

    learning_request = {
        "operation": "autonomous-learn",
        "operation_id": "owner-autonomous-location",
        "goal": "acquire location language",
        "opportunities": [
            {
                "candidate_id": "owner-location",
                "learning_kind": "construction",
                "expected_gain": 4.0,
                "novelty": 1.0,
                "request": {
                    "construction_id": "owner-location-assertion",
                    "examples": [
                        {
                            "text": "the key is in the drawer",
                            "bindings": {"item": "key", "place": "drawer"},
                        },
                        {
                            "text": "the cup is in the box",
                            "bindings": {"item": "cup", "place": "box"},
                        },
                    ],
                    "meaning": {
                        "object": {"$role": "place"},
                        "relation": "located-in",
                        "subject": {"$role": "item"},
                    },
                    "speech_act": "assertion",
                },
            }
        ],
    }
    home = tmp_path / "autonomous"
    with FieldIntelligenceOwner(home) as owner:
        call(owner, "configure", "configure")
        call(
            owner,
            "submit-autonomous-learning",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments=learning_request,
            steps=4096,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["selected"]["candidate_id"] == "owner-location"
        assert result["learning"]["learning_kind"] == "construction"
        event_id = result["event"]["id"]

    with FieldIntelligenceOwner(home) as owner:
        task = owner.state.computers[0].inspect()["task"]
        assert task["current"]["Event"][event_id]["id"] == event_id
 
def test_owner_autonomous_learning_discovers_resident_action_schema(tmp_path) -> None:
    def atom(value: str) -> dict[str, Any]:
        return {
            "kind": "atom",
            "type": {"kind": "named", "name": "entity"},
            "value": value,
        }

    def episode(event_id: str, source_id: str, left: str, right: str) -> dict[str, Any]:
        return {
            "event_id": event_id,
            "source_revision_id": event(source_id),
            "action": {
                "kind": "constructor",
                "name": "move",
                "args": [atom(left), atom(right)],
            },
            "post_state": {"kind": "record", "fields": {"at": atom(right)}},
            "bindings": {},
            "observation": {"success": True},
        }

    with FieldIntelligenceOwner(tmp_path / "resident-discovery") as owner:
        call(owner, "configure", "configure")
        for index, raw in enumerate(
            (
                episode("owner-resident-e1", "owner-resident-s1", "a", "b"),
                episode("owner-resident-e2", "owner-resident-s2", "c", "d"),
            )
        ):
            source = SourceInput(
                source_id=f"owner-resident-source-{index}",
                content=canonical_json_bytes(episode_source_payload(raw)),
                media_type="application/json",
                codec="utf-8",
                observed_timestamp="now",
                scope="test",
                claim_category="observation",
                fidelity="exact",
            )
            revision = owner.archive_source(
                operation_id=f"archive-owner-resident-{index}",
                source=source,
                context={},
            )["source"]["revision_id"]
            grounded = {
                **raw,
                "source_revision_id": revision,
                "source_revision_ids": [revision],
            }
            request = {
                "operation": "admit-open-vocab-episode",
                "operation_id": f"admit-owner-resident-{index}",
                "event_id": raw["event_id"],
                "source_revision_id": revision,
                "episode": grounded,
            }
            if index == 0:
                call(
                    owner,
                    f"admit-owner-resident-{index}",
                    "submit",
                    kernel="cognition.field",
                    state=semantic_cognition_state(),
                    arguments=request,
                    steps=4096,
                )
            else:
                call(
                    owner,
                    f"admit-owner-resident-{index}",
                    "invoke",
                    arguments=request,
                    steps=1024,
                )
            assert owner.state.computers[0].inspect()["consumed_result"]["status"] == (
                "supported"
            )

        call(
            owner,
            "discover-owner-resident-schema",
            "invoke",
            arguments={
                "operation": "autonomous-learn",
                "operation_id": "discover-owner-resident-schema",
                "goal": "acquire a movement schema",
            },
            steps=4096,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["discovery"]["opportunity_count"] == 1
        assert result["selected"]["learning_kind"] == "action-schema"
        assert result["learning"]["admission"]["schema_ref"]["kind"] == "Program"


def test_owner_autonomous_learning_discovers_resident_procedure(tmp_path) -> None:
    def atom(value: str) -> dict[str, Any]:
        return {
            "kind": "atom",
            "type": {"kind": "named", "name": "entity"},
            "value": value,
        }

    def episode(
        event_id: str,
        source_id: str,
        trajectory_id: str,
        trajectory_index: int,
        operation: str,
        item: str,
        place: str,
    ) -> dict[str, Any]:
        action = {
            "kind": "constructor",
            "name": operation,
            "args": [atom(item)] if operation != "move" else [atom(item), atom(place)],
        }
        return {
            "event_id": event_id,
            "source_revision_id": event(source_id),
            "trajectory_id": trajectory_id,
            "trajectory_index": trajectory_index,
            "action": action,
            "post_state": {"kind": "record", "fields": {"at": atom(place)}},
            "bindings": {"item": atom(item)},
            "observation": {"success": True},
        }

    rows = [
        episode("owner-route-a0", "owner-route-a-s0", "owner-route-a", 0, "open", "a", "a"),
        episode("owner-route-a1", "owner-route-a-s1", "owner-route-a", 1, "move", "a", "left"),
        episode("owner-route-a2", "owner-route-a-s2", "owner-route-a", 2, "check", "a", "a"),
        episode("owner-route-a3", "owner-route-a-s3", "owner-route-a", 3, "close", "a", "a"),
        episode("owner-route-b0", "owner-route-b-s0", "owner-route-b", 0, "open", "u", "u"),
        episode("owner-route-b1", "owner-route-b-s1", "owner-route-b", 1, "move", "u", "right"),
        episode("owner-route-b2", "owner-route-b-s2", "owner-route-b", 2, "check", "u", "u"),
        episode("owner-route-b3", "owner-route-b-s3", "owner-route-b", 3, "close", "u", "u"),
    ]

    owner_home = tmp_path / "resident-procedure"
    with FieldIntelligenceOwner(owner_home) as owner:
        call(owner, "configure", "configure")
        for index, raw in enumerate(rows):
            source = SourceInput(
                source_id=f"owner-route-source-{index}",
                content=canonical_json_bytes(episode_source_payload(raw)),
                media_type="application/json",
                codec="utf-8",
                observed_timestamp="now",
                scope="test",
                claim_category="observation",
                fidelity="exact",
            )
            revision = owner.archive_source(
                operation_id=f"archive-owner-route-{index}",
                source=source,
                context={},
            )["source"]["revision_id"]
            grounded = {
                **raw,
                "source_revision_id": revision,
                "source_revision_ids": [revision],
            }
            request = {
                "operation": "admit-open-vocab-episode",
                "operation_id": f"admit-owner-route-{index}",
                "event_id": raw["event_id"],
                "source_revision_id": revision,
                "episode": grounded,
            }
            call(
                owner,
                f"admit-owner-route-{index}",
                "submit" if index == 0 else "invoke",
                **(
                    {
                        "kernel": "cognition.field",
                        "state": semantic_cognition_state(),
                        "arguments": request,
                        "steps": 4096,
                    }
                    if index == 0
                    else {"arguments": request, "steps": 1024}
                ),
            )
            assert owner.state.computers[0].inspect()["consumed_result"]["status"] == (
                "supported"
            )

        call(
            owner,
            "discover-owner-resident-procedure",
            "invoke",
            arguments={
                "operation": "autonomous-learn",
                "operation_id": "discover-owner-resident-procedure",
                "goal": "acquire a recurring route procedure",
            },
            steps=4096,
        )
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["selected"]["learning_kind"] == "procedure"
        assert result["learning"]["procedure"]["kind"] == "Program"

        call(
            owner,
            "invoke-owner-resident-procedure",
            "invoke",
            arguments={
                "operation": "invoke-procedure",
                "procedure_ref": result["learning"]["procedure"],
                "bindings": {"role_0": "new-item", "role_1": "new-place"},
            },
            steps=1024,
        )
        invocation = owner.state.computers[0].inspect()["consumed_result"]
        assert invocation["status"] == "supported"
        assert len(invocation["proposed_actions"]) == 4
        call(
            owner,
            "plan-owner-resident-procedure",
            "invoke",
            arguments={
                "operation": "plan-procedure",
                "procedure_ref": result["learning"]["procedure"],
                "bindings": {"role_0": "new-item", "role_1": "new-place"},
                "goal": invocation["outcome"]["procedure_postconditions"],
                "plan_id": "owner-resident-route-plan",
                "scope": "sandbox",
                "target": "owner-route-execution",
            },
            steps=1024,
        )
        planned = owner.state.computers[0].inspect()["consumed_result"]
        assert planned["status"] == "supported"
        assert planned["proposal"]["action"]["operation"] == "invoke-procedure"
        proposal = planned["proposal"]
        grant = AuthorityGrant(
            grant_id="owner-procedure-grant",
            issuer="owner-procedure-test",
            generation=owner.authority_generation,
            operation="computer-effect",
            target="owner-route-execution",
            scope="sandbox",
        )
        call(
            owner,
            "authorize-owner-resident-procedure",
            "authorized-invoke",
            arguments={
                "operation": "authorize-action",
                "proposal_id": proposal["proposal_id"],
            },
            grant=grant.as_dict(),
            target="owner-route-execution",
            scope="sandbox",
            steps=1024,
        )
        call(
            owner,
            "dispatch-owner-resident-procedure",
            "authorized-invoke",
            arguments={
                "operation": "dispatch-action",
                "proposal_id": proposal["proposal_id"],
                "adapter_id": "owner-procedure-adapter",
                "dispatch_id": "dispatch:owner-procedure",
                "idempotency": "guaranteed",
                "idempotency_key": "idempotency:owner-procedure",
            },
            grant=grant.as_dict(),
            target="owner-route-execution",
            scope="sandbox",
            steps=1024,
        )
        call(
            owner,
            "ack-owner-resident-procedure",
            "invoke",
            arguments={
                "operation": "acknowledgment",
                "event_id": "d" * 64,
                "observation": {"location": "left"},
                "observation_verified": True,
                "proposal_id": proposal["proposal_id"],
                "status": "succeeded",
            },
            steps=1024,
        )
        acknowledged = owner.state.computers[0].inspect()["consumed_result"]
        assert acknowledged["status"] == "supported"
        assert acknowledged["next_proposal"]["action"]["step_index"] == 1
        assert acknowledged["next_proposal"]["action"]["context"][
            "procedure_feedback"
        ] == {
            "event": acknowledged["event"],
            "index": 0,
            "observation": {"location": "left"},
            "observation_verified": True,
            "status": "succeeded",
        }
        owner.close()
        owner = FieldIntelligenceOwner(owner_home)
        acknowledged = owner.state.computers[0].inspect()["consumed_result"]
        assert acknowledged["next_proposal"]["action"]["step_index"] == 1
        for step_index in range(1, 4):
            proposal = acknowledged["next_proposal"]
            assert proposal["action"]["step_index"] == step_index
            step_grant = AuthorityGrant(
                grant_id=f"owner-procedure-grant-{step_index}",
                issuer="owner-procedure-test",
                generation=owner.authority_generation,
                operation="computer-effect",
                target="owner-route-execution",
                scope="sandbox",
            )
            call(
                owner,
                f"authorize-owner-resident-procedure-{step_index}",
                "authorized-invoke",
                arguments={
                    "operation": "authorize-action",
                    "proposal_id": proposal["proposal_id"],
                },
                grant=step_grant.as_dict(),
                target="owner-route-execution",
                scope="sandbox",
                steps=1024,
            )
            call(
                owner,
                f"dispatch-owner-resident-procedure-{step_index}",
                "authorized-invoke",
                arguments={
                    "operation": "dispatch-action",
                    "proposal_id": proposal["proposal_id"],
                    "adapter_id": "owner-procedure-adapter",
                    "dispatch_id": f"dispatch:owner-procedure:{step_index}",
                    "idempotency": "guaranteed",
                    "idempotency_key": f"idempotency:owner-procedure:{step_index}",
                },
                grant=step_grant.as_dict(),
                target="owner-route-execution",
                scope="sandbox",
                steps=1024,
            )
            call(
                owner,
                f"ack-owner-resident-procedure-{step_index}",
                "invoke",
                arguments={
                    "operation": "acknowledgment",
                    "event_id": f"{step_index:x}" * 64,
                    "proposal_id": proposal["proposal_id"],
                    "status": "succeeded",
                },
                steps=1024,
            )
            acknowledged = owner.state.computers[0].inspect()["consumed_result"]
            assert acknowledged["status"] == "supported"
            if step_index < 3:
                assert acknowledged["next_proposal"]["action"]["step_index"] == (
                    step_index + 1
                )
            else:
                assert acknowledged["next_proposal"] is None
