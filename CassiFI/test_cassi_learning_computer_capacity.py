"""Public owner-surface regressions for regional value capacity planning."""
from __future__ import annotations

from typing import Any, Mapping

import pytest

import cassi_field_regions as field_regions
from cassi_field_atlas import FieldIntelligenceError
from cassi_field_cognition import semantic_cognition_state
from cassi_field_owner import (
    CapacityLimits,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
)
from cassi_learning_computer import LearningComputer, LearningComputerError



def call(
    owner: FieldIntelligenceOwner,
    computer_id: str,
    request_id: str,
    action: str,
    **arguments: Any,
) -> Mapping[str, Any]:
    return FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": request_id,
            "operation": "computer",
            "params": {
                "operation_id": request_id,
                "computer_id": computer_id,
                "action": action,
                "arguments": arguments,
            },
        }
    )


def capacities(owner: FieldIntelligenceOwner) -> dict[str, int]:
    computer = owner.state.computers[0]
    machine = computer._controller().inspect(computer.field)
    by_slot = {row["slot"]: row for row in machine["regions"]}
    result: dict[str, int] = {}
    for name, object_id in machine["named_values"].items():
        reference = field_regions._resolve_object(
            computer.field._field.reshape(-1),
            computer.profile,
            object_id,
            right=field_regions.RIGHT_WRITE,
        )
        result[name] = by_slot[reference.slot]["capacity_words"]
    return result


def test_public_profiles_pin_historical_default_and_small_capacities(
    tmp_path,
) -> None:
    historical = {
        "arguments": 16_384,
        "communication_receiver_a": 4_096,
        "communication_receiver_b": 4_096,
        "config": 1_024,
        "frames": 98_304,
        "outcome": 98_304,
        "policy": 24_576,
        "result": 98_304,
        "session": 16_384,
        "task": 98_304,
    }
    with FieldIntelligenceOwner(tmp_path / "default") as owner:
        call(owner, "default", "default-configure", "configure")
        assert owner.state.computers[0].profile.mode_count == 65_536
        assert capacities(owner) == historical
        assert owner.state.computers[0].inspect()["status"] != "faulted"

    small_limits = CapacityLimits(
        max_state_bytes=2_000_000,
        max_workspace_bytes=2_000_000,
    )
    small = {
        "arguments": 256,
        "communication_receiver_a": 16,
        "communication_receiver_b": 16,
        "config": 128,
        "frames": 512,
        "outcome": 512,
        "policy": 10_240,
        "result": 512,
        "session": 256,
        "task": 512,
    }
    with FieldIntelligenceOwner(
        tmp_path / "small", limits=small_limits
    ) as owner:
        call(
            owner,
            "small",
            "small-configure",
            "configure",
            profile={
                "program_capacity": 16,
                "stack_capacity": 16,
                "max_steps": 100,
            },
        )
        assert owner.state.computers[0].profile.mode_count == 2_000
        assert capacities(owner) == small
        assert owner.state.computers[0].inspect()["status"] != "faulted"


def test_large_public_profile_scales_and_completes_observation_query(
    tmp_path,
) -> None:
    historical_task_words = 98_304
    with FieldIntelligenceOwner(tmp_path / "large") as owner:
        call(
            owner,
            "large",
            "large-configure",
            "configure",
            profile={"mode_count": 131_072},
        )
        planned = capacities(owner)
        assert planned["task"] >= historical_task_words
        assert planned["task"] == 196_608

        submitted = call(
            owner,
            "large",
            "large-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "observe-large",
                "delivery_id": "delivery-large",
                "event_id": "event-large",
                "observations": [
                    {
                        "binding_id": "probe",
                        "subject": "probe",
                        "attribute": "reading",
                        "value": 42,
                    }
                ],
            },
            steps=128,
        )
        assert submitted["result"]["receipt"]["schema"] == (
            "cassifi.learning-computer-submit-receipt.v1"
        )
        after_submit = owner.state.computers[0].inspect()
        assert after_submit["status"] != "faulted"
        assert after_submit["consumed_result"]["operation"] == "observe"
        assert after_submit["consumed_result"]["status"] == "supported"

        call(
            owner,
            "large",
            "large-query",
            "invoke",
            arguments={
                "operation": "query",
                "operation_id": "query-large",
                "query": {"kind": "binding", "binding_id": "probe"},
            },
            steps=128,
        )
        after_query = owner.state.computers[0].inspect()
        assert after_query["status"] != "faulted"
        assert after_query["consumed_result"]["operation"] == "query"
        assert after_query["consumed_result"]["status"] == "supported"
        assert after_query["consumed_result"]["answer"] == 42


def test_resident_child_interrupt_restart_return_and_parent_preservation(
    tmp_path,
) -> None:
    root = tmp_path / "resident-call"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "main", "call-configure", "configure")
        call(
            owner,
            "main",
            "parent-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "parent-observe",
                "delivery_id": "parent-delivery",
                "event_id": "parent-event",
                "observations": [
                    {
                        "binding_id": "parent-value",
                        "subject": "parent",
                        "attribute": "value",
                        "value": 7,
                    }
                ],
            },
            steps=128,
        )
        started = call(
            owner,
            "main",
            "child-call",
            "call",
            call_id="child-observation",
            kernel="cognition.field",
            state=semantic_cognition_state(scope="child"),
            return_binding="child-result",
            arguments={
                "operation": "observe",
                "operation_id": "child-observe",
                "delivery_id": "child-delivery",
                "event_id": "child-event",
                "observations": [
                    {
                        "binding_id": "child-value",
                        "subject": "child",
                        "attribute": "value",
                        "value": 11,
                    }
                ],
            },
            steps=1,
        )
        assert started["result"]["receipt"]["run"]["status"] == "running"
        assert owner.state.computers[0].inspect()["invocation_depth"] == 1
        paused_sha256 = owner.state.state_sha256

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == paused_sha256
        assert owner.state.computers[0].inspect()["invocation_depth"] == 1
        returned = call(
            owner, "main", "child-finish", "advance", steps=128
        )
        assert returned["result"]["receipt"]["status"] == "returned"
        inspected = owner.state.computers[0].inspect()
        assert inspected["invocation_depth"] == 0
        child = inspected["task"]["invocation_returns"]["child-result"]
        assert child["status"] == "halted"
        assert child["result"]["operation"] == "observe"
        queried = call(
            owner,
            "main",
            "parent-query",
            "invoke",
            arguments={
                "operation": "query",
                "operation_id": "parent-query-operation",
                "query": {
                    "kind": "binding",
                    "binding_id": "parent-value",
                },
            },
            steps=128,
        )
        assert queried["result"]["receipt"]["run"]["status"] == "waiting"
        result = owner.state.computers[0].inspect()["consumed_result"]
        assert result["status"] == "supported"
        assert result["answer"] == 7


def test_reasoning_and_self_development_use_resident_return_semantics(
    tmp_path,
) -> None:
    root = tmp_path / "episodes"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "episodes", "episodes-configure", "configure")
        call(
            owner,
            "episodes",
            "episodes-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={
                "operation": "observe",
                "operation_id": "episodes-observe",
                "delivery_id": "episodes-delivery",
                "event_id": "episodes-event",
                "observations": [
                    {
                        "binding_id": "known-value",
                        "subject": "workshop",
                        "attribute": "setting",
                        "value": 7,
                    }
                ],
            },
            steps=128,
        )
        call(
            owner,
            "episodes",
            "reasoning-begin",
            "invoke",
            arguments={
                "operation": "begin-reasoning",
                "operation_id": "reasoning-begin-semantic",
                "episode_id": "answer-setting",
                "question": {"binding_id": "known-value"},
                "request": {
                    "operation": "query",
                    "operation_id": "reasoning-child-query",
                    "query": {
                        "kind": "binding",
                        "binding_id": "known-value",
                    },
                },
                "allocation": {
                    "evidence_reads": 0,
                    "model_calls": 0,
                    "storage_words": 64,
                    "work": 32,
                },
            },
            steps=128,
        )
        invocation = owner.state.computers[0].inspect()[
            "consumed_result"
        ]["invocation"]
        call(
            owner,
            "episodes",
            "reasoning-call",
            "call",
            **invocation,
            steps=1,
        )
        assert owner.state.computers[0].inspect()["invocation_depth"] == 1
        reasoning_pause = owner.state.state_sha256

    with FieldIntelligenceOwner(root) as owner:
        assert owner.state.state_sha256 == reasoning_pause
        call(owner, "episodes", "reasoning-return", "advance", steps=128)
        call(
            owner,
            "episodes",
            "reasoning-finish",
            "invoke",
            arguments={
                "operation": "finish-reasoning",
                "operation_id": "reasoning-finish-semantic",
                "episode_id": "answer-setting",
            },
            steps=128,
        )
        reasoning = owner.state.computers[0].inspect()["consumed_result"]
        assert reasoning["status"] == "supported"
        assert reasoning["result"]["answer"] == 7
        assert reasoning["episode"]["kind"] == "Obligation"

        call(
            owner,
            "episodes",
            "development-start",
            "invoke",
            arguments={
                "operation": "start-development",
                "operation_id": "development-start-semantic",
                "episode_id": "reflect-setting",
                "capability_target": {"binding_id": "known-value"},
                "diagnosis": "method-selection",
                "remit": {"purpose": "improve-current-reasoning"},
                "available_information": {"source_revision_ids": []},
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
                "assessment": {"actual": 7, "predicted": 7},
                "stopping_condition": {"max_attempts": 1},
            },
            steps=128,
        )
        development = owner.state.computers[0].inspect()[
            "consumed_result"
        ]
        assert development["selected_skill"] == "reflect"
        call(
            owner,
            "episodes",
            "development-call",
            "call",
            **development["invocation"],
            steps=128,
        )
        call(
            owner,
            "episodes",
            "development-finish",
            "invoke",
            arguments={
                "operation": "finish-development",
                "operation_id": "development-finish-semantic",
                "episode_id": "reflect-setting",
            },
            steps=128,
        )
        finished = owner.state.computers[0].inspect()["consumed_result"]
        assert finished["status"] == "supported"
        assert finished["result"]["selected_skill"] == "reflect"
        assert finished["assessment"]["kind"] == "Assessment"

        call(
            owner,
            "episodes",
            "development-reopen",
            "invoke",
            arguments={
                "operation": "reopen-development",
                "operation_id": "development-reopen-semantic",
                "episode_id": "reflect-setting",
                "allocation": {
                    "evidence_reads": 0,
                    "model_calls": 0,
                    "storage_words": 128,
                    "work": 16,
                },
                "justification": {
                    "kind": "new-allocation",
                    "detail": "smaller retained replication",
                },
            },
            steps=128,
        )
        reopened = owner.state.computers[0].inspect()["consumed_result"]
        assert reopened["status"] == "supported"
        assert reopened["episode"]["content_version"] == 3


def test_public_capacity_refusal_keeps_owner_usable(tmp_path) -> None:
    with pytest.raises(
        LearningComputerError,
        match="^regional image does not fit the declared workspace$",
    ):
        LearningComputer.initial(
            "direct-refusal",
            profile={"mode_count": 65_536, "registry_words": 400_000},
        )

    with FieldIntelligenceOwner(tmp_path / "refusal") as owner:
        before = owner.state.state_sha256
        with pytest.raises(FieldIntelligenceError) as error:
            call(
                owner,
                "refusal",
                "refuse-too-many-values",
                "configure",
                profile={"mode_count": 65_536, "registry_words": 400_000},
            )
        assert type(error.value) is FieldIntelligenceError
        assert error.value.code == "INVALID_COMPUTER"
        assert str(error.value) == (
            "regional image does not fit the declared workspace"
        )
        assert owner.state.state_sha256 == before
        assert owner.state.computers == ()

        call(owner, "refusal", "recovery-configure", "configure")
        computer = owner.state.computers[0]
        assert computer.profile.mode_count == 65_536
        assert computer.inspect()["status"] != "faulted"


def test_settled_owner_invocation_is_atomic_replayable_and_capacity_safe(
    tmp_path,
) -> None:
    root = tmp_path / "settled"
    with FieldIntelligenceOwner(root) as owner:
        call(owner, "settled", "settled-configure", "configure")
        call(
            owner,
            "settled",
            "settled-submit",
            "submit",
            kernel="cognition.field",
            state=semantic_cognition_state(),
            arguments={"operation": "inspect", "operation_id": "seed"},
            steps=64,
        )
        before_generation = owner.state.generation
        settled = call(
            owner,
            "settled",
            "settled-inspect",
            "invoke-settled",
            arguments={
                "operation": "inspect",
                "operation_id": "settled-inspect-semantic",
            },
        )
        receipt = settled["result"]["receipt"]
        assert receipt["schema"] == (
            "cassifi.learning-computer-invoke-settled-receipt.v1"
        )
        assert receipt["consumed_result"]["status"] == "supported"
        assert receipt["quanta"] >= 1
        assert owner.state.generation == before_generation + 1
        settled_sha256 = owner.state.state_sha256
        capacity = owner.state.computers[0].inspect()["region_capacity"]
        assert capacity["task"]["available_words"] == (
            capacity["task"]["capacity_words"]
            - capacity["task"]["used_words"]
        )

        replay = call(
            owner,
            "settled",
            "settled-inspect",
            "invoke-settled",
            arguments={
                "operation": "inspect",
                "operation_id": "settled-inspect-semantic",
            },
        )
        assert replay["result"]["receipt"] == receipt
        assert replay["result"]["checkpoint_receipt"]["replayed"] is True
        assert owner.state.state_sha256 == settled_sha256
        assert owner.state.generation == before_generation + 1

        with pytest.raises(FieldIntelligenceError) as error:
            call(
                owner,
                "settled",
                "settled-too-large",
                "invoke-settled",
                arguments={
                    "operation": "inspect",
                    "operation_id": "settled-too-large-semantic",
                    "padding": "x" * 1_000_000,
                },
            )
        assert error.value.code == "WORK_CAPACITY"
        assert "regional capacity" in str(error.value)
        assert owner.state.state_sha256 == settled_sha256
        assert owner.state.generation == before_generation + 1

        recovered = call(
            owner,
            "settled",
            "settled-after-refusal",
            "invoke-settled",
            arguments={
                "operation": "inspect",
                "operation_id": "settled-after-refusal-semantic",
            },
        )
        assert recovered["result"]["receipt"]["consumed_result"]["status"] == (
            "supported"
        )
        final_sha256 = owner.state.state_sha256

    with FieldIntelligenceOwner(root) as reopened:
        assert reopened.state.state_sha256 == final_sha256
        assert (
            reopened.state.computers[0].inspect()["consumed_result"]["status"]
            == "supported"
        )
