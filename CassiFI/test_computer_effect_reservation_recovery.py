"""Focused persistence coverage for regional computer-effect reservations."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from cassi_field_atlas import FieldIntelligenceError, canonical_json_bytes, sha256_value
from cassi_field_cognition import regional_sustained_episode_state
from cassi_field_owner import (
    AuthorityGrant,
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
    SourceInput,
)


TARGET = "calibration-valve-7"
SCOPE = "workshop:bay-17"


def computer_call(
    owner: FieldIntelligenceOwner,
    operation_id: str,
    action: str,
    **arguments: Any,
) -> dict[str, Any]:
    return dict(
        FieldIntelligenceSurface(owner)
        .handle(
            {
                "schema": RPC_SCHEMA,
                "request_id": operation_id,
                "operation": "computer",
                "params": {
                    "operation_id": operation_id,
                    "computer_id": "main",
                    "action": action,
                    "arguments": arguments,
                },
            }
        )["result"]
    )


def _create_reserved_checkpoint(root: Path) -> dict[str, Any]:
    owner = FieldIntelligenceOwner(root)
    try:
        source = SourceInput(
            source_id="focused-recovery-source",
            content=canonical_json_bytes(
                {"instrument": "north-gauge", "location": "bay-seven"}
            ),
            media_type="application/json",
            codec="utf-8",
            observed_timestamp="focused-recovery-time",
            scope=SCOPE,
            claim_category="controlled-observation",
            fidelity="exact-record",
            labels=("test",),
        )
        archived = owner.archive_source(
            operation_id="episode-observation",
            source=source,
            context={},
            event_kind="workshop-observation",
        )
        revision_id = archived["source"]["revision_id"]
        computer_call(
            owner,
            "configure",
            "configure",
            profile={"program_capacity": 16, "stack_capacity": 16, "max_steps": 100},
        )
        task = regional_sustained_episode_state(
            instrument_alias="north-gauge",
            location_alias="bay-seven",
            access_allowed=False,
            source_revision_id=revision_id,
            action_target=TARGET,
            action_scope=SCOPE,
            numeric_work=(2.0, 3.0, 5.0),
        )
        started = computer_call(
            owner,
            "episode-submit",
            "submit",
            kernel="cognition.field",
            state=task,
            steps=128,
        )
        assert started["receipt"]["run"]["status"] == "waiting"
        assert (
            owner.state.computers[0].inspect()["task"]["continuation"]["stage"]
            == "await-premise"
        )
        revised = computer_call(
            owner,
            "episode-premise-change",
            "invoke",
            arguments={
                "operation": "premise-change",
                "event_id": "b" * 64,
                "source_revision_id": revision_id,
                "access_allowed": True,
            },
            steps=128,
        )
        assert revised["receipt"]["run"]["status"] == "waiting"
        continuation = owner.state.computers[0].inspect()["task"]["continuation"]
        assert continuation["stage"] == "await-authorization"
        proposal = continuation["proposal"]
        proposal_id = proposal["proposal_id"]
        assert "operation_id" not in proposal

        grant = AuthorityGrant(
            grant_id="episode-grant",
            issuer="focused-recovery-test",
            generation=owner.authority_generation,
            operation="computer-effect",
            target=TARGET,
            scope=SCOPE,
            one_use=True,
        )
        authorized = computer_call(
            owner,
            "episode-authorize",
            "authorized-invoke",
            arguments={"operation": "authorize-action", "proposal_id": proposal_id},
            grant=grant.as_dict(),
            target=TARGET,
            scope=SCOPE,
            steps=128,
        )
        assert authorized["receipt"]["run"]["status"] == "waiting"
        dispatched = computer_call(
            owner,
            "episode-dispatch",
            "authorized-invoke",
            arguments={
                "operation": "dispatch-action",
                "proposal_id": proposal_id,
                "adapter_id": "workshop-adapter",
                "dispatch_id": "dispatch:focused-recovery",
                "idempotency": "guaranteed",
                "idempotency_key": "idempotency:focused-recovery",
            },
            grant=grant.as_dict(),
            target=TARGET,
            scope=SCOPE,
            steps=128,
        )
        assert dispatched["receipt"]["run"]["status"] == "waiting"
        assert (
            owner.state.computers[0].inspect()["task"]["continuation"]["stage"]
            == "await-acknowledgment"
        )
        control = json.loads(owner.authority_path.read_text(encoding="utf-8"))
        binding = control["used_grant_bindings"][grant.grant_id]
        assert binding["prediction_id"] == proposal_id
        assert binding["request"]["operation_id"] == proposal_id
        return {
            "computer_state_sha256": owner.state.computers[0].state_sha256,
            "owner_state_sha256": owner.state.state_sha256,
            "grant_id": grant.grant_id,
            "proposal_id": proposal_id,
            "binding": binding,
        }
    finally:
        owner.close()


def test_dispatched_regional_effect_reopens_with_reservation_intact(tmp_path: Path) -> None:
    root = tmp_path / "owner"
    checkpoint = _create_reserved_checkpoint(root)

    with FieldIntelligenceOwner(root) as reopened:
        assert reopened.state.state_sha256 == checkpoint["owner_state_sha256"]
        assert (
            reopened.state.computers[0].state_sha256
            == checkpoint["computer_state_sha256"]
        )
        continuation = reopened.state.computers[0].inspect()["task"]["continuation"]
        assert continuation["stage"] == "await-acknowledgment"
        assert continuation["proposal"]["proposal_id"] == checkpoint["proposal_id"]
        control = json.loads(reopened.authority_path.read_text(encoding="utf-8"))
        assert checkpoint["grant_id"] in control["used_grant_ids"]
        assert checkpoint["grant_id"] in control["used_grant_bindings"]
        assert (
            control["used_grant_bindings"][checkpoint["grant_id"]]
            == checkpoint["binding"]
        )


def test_reopen_rejects_different_reserved_dispatch_request(tmp_path: Path) -> None:
    root = tmp_path / "owner"
    checkpoint = _create_reserved_checkpoint(root)
    authority_path = root / "authority-control.json"
    control = json.loads(authority_path.read_text(encoding="utf-8"))
    binding = control["used_grant_bindings"][checkpoint["grant_id"]]
    binding["request"]["payload"]["dispatch_id"] = "dispatch:tampered"
    binding["request_sha256"] = sha256_value(binding["request"])
    authority_path.write_bytes(canonical_json_bytes(control))

    with pytest.raises(FieldIntelligenceError) as error:
        FieldIntelligenceOwner(root)
    assert error.value.code == "PERSISTENCE_CORRUPT"
