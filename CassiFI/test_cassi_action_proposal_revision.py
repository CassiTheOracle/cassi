"""Regression: a record revision must not strand an action proposal's warrant.

A live action proposal keeps current-version pointers to its obligation,
acknowledgment, and outcome assessment.  Revision publishes a new content version
under an unchanged identity, so the recorded defect left the proposal pointing at
a superseded obligation version and the whole cognition state stopped validating:
the next dependent correction refused with INVALID_SEMANTIC_REFERENCE and rolled
back, so the correction could never publish.  The public path must instead
reconcile the pointer and retire a proposal whose warrant stopped being active.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

import pytest

import cassi_field_cognition
from cassi_field_atlas import FieldIntelligenceError
from cassi_field_cognition import semantic_cognition_state
from cassi_field_owner import (
    FieldIntelligenceOwner,
    FieldIntelligenceSurface,
    RPC_SCHEMA,
)

COMPUTER_PROFILE = {"program_capacity": 4096, "stack_capacity": 256, "max_steps": 4096}
AFFORDANCE = {
    "action_context_support": [],
    "argument_roles": [
        {
            "binding_constraints": {},
            "bounds": None,
            "name": name,
            "required": True,
            "units": None,
            "value_type": "string",
        }
        for name in ("kind", "question", "question_id")
    ],
    "effects": {
        "expected_observations": [],
        "failure_modes": [],
        "intended": {},
        "possible_side_effects": [],
    },
    "execution": {
        "concurrency": {"mode": "exclusive"},
        "duration": {"lower": 0.0, "units": "step", "upper": 1.0},
        "resource_occupancy": [],
        "termination_conditions": [],
    },
    "obligations": {
        "authority": ["synthetic-only"],
        "disclosure": [],
        "source_access": [],
    },
    "preconditions": {
        "latent": [],
        "observable": [],
        "probability_model": None,
        "semantics": "set",
    },
    "program": {
        "applicability": {},
        "arguments": {},
        "body": {"steps": [{"kind": "probe-inquiry"}]},
        "bounds": {"max_branches": 64, "max_horizon": 1, "max_work": 1},
        "effects": {"emits": [], "reads": [], "writes": []},
        "guards": [],
        "program_kind": "procedure",
        "schema": "cassifi.semantic-program-payload.v1",
    },
    "program_role": "affordance",
    "reversibility": {"compensation": None, "mode": "reversible"},
    "risk": {"minimum": 0.0, "possible_harms": [], "units": "risk-score"},
}
ALTERNATIVES = [{"u": -1}, {"u": 0}, {"u": 1}]
QUESTIONS = [
    {
        "cost": 0.1,
        "outcomes": {"nonzero": [{"u": -1}, {"u": 1}], "zero": [{"u": 0}]},
        "question": "does the dial offset the observed difference",
        "question_id": "probe-difference-sign",
        "risk": 0.05,
    }
]


def rpc(
    owner: FieldIntelligenceOwner,
    computer_id: str,
    operation_id: str,
    action: str,
    arguments: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "operation_id": operation_id,
        "computer_id": computer_id,
        "action": action,
    }
    if arguments is not None:
        params["arguments"] = dict(arguments)
    return dict(
        FieldIntelligenceSurface(owner).handle(
            {
                "schema": RPC_SCHEMA,
                "request_id": operation_id,
                "operation": "computer",
                "params": params,
            }
        )
    )


def task(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    return dict(owner.inspect_computers()["computers"][0]["task"])


def consumed(owner: FieldIntelligenceOwner, computer_id: str) -> dict[str, Any]:
    rows = owner.inspect_computers()["computers"]
    row = next(item for item in rows if item.get("computer_id") == computer_id)
    result = row.get("consumed_result")
    assert isinstance(result, Mapping), row
    return dict(result)


def task_sha256(owner: FieldIntelligenceOwner) -> str:
    return str(owner.inspect_computers()["computers"][0]["task_state_sha256"])


def pausing_inquiry(
    tmp_path: Path, label: str
) -> tuple[FieldIntelligenceOwner, str]:
    owner = FieldIntelligenceOwner(tmp_path / label)
    computer_id = f"computer-{label}"
    rpc(
        owner,
        computer_id,
        f"{label}-configure",
        "configure",
        {"profile": COMPUTER_PROFILE},
    )
    rpc(
        owner,
        computer_id,
        f"{label}-seed",
        "submit",
        {
            "kernel": "cognition.field",
            "kind": "semantic",
            "state": semantic_cognition_state(
                scope={"world": "proposal-revision"},
                frame={"task": "dependent-correction"},
            ),
            "arguments": {
                "operation": "inspect",
                "operation_id": f"{label}-seed-inspect",
            },
        },
    )
    rpc(
        owner,
        computer_id,
        f"{label}-register",
        "invoke",
        {
            "arguments": {
                "kind": "Program",
                "operation": "register",
                "operation_id": f"{label}-register-dial",
                "payload": AFFORDANCE,
                "record_id": "dial",
            },
            "steps": 256,
        },
    )
    rpc(
        owner,
        computer_id,
        f"{label}-inquire",
        "invoke",
        {
            "arguments": {
                "affordance_id": "dial",
                "alternatives": ALTERNATIVES,
                "context": {},
                "operation": "inquire",
                "operation_id": f"{label}-inquire",
                "questions": QUESTIONS,
                "scope": "synthetic-only",
                "target": "nonexistent-diagnostic-plant",
            },
            "steps": 512,
        },
    )
    return owner, computer_id


def correction_request(label: str, target: Mapping[str, Any]) -> dict[str, Any]:
    return {
        "arguments": {
            "correction_id": f"{label}-dial-calibration",
            "operation": "correct",
            "operation_id": f"{label}-correct-dial",
            "reason": "dependent correction of the affordance",
            "replacement": {
                "risk": {"minimum": 0.25, "possible_harms": [], "units": "risk-score"}
            },
            "target": dict(target),
        },
        "steps": 512,
    }


def current_obligation_state(owner: FieldIntelligenceOwner) -> dict[str, Any]:
    inspection = task(owner)
    proposal = inspection["continuation"]["proposal"]
    obligation_ref = proposal["obligation"]
    record = inspection["records"][obligation_ref["id"]][-1]
    return {
        "proposal": proposal,
        "obligation_ref": obligation_ref,
        "obligation_status": record["status"],
        "obligation_version": record["content_version"],
    }


def test_correction_reconciles_the_retired_proposal_warrant(tmp_path: Path) -> None:
    owner, computer_id = pausing_inquiry(tmp_path, "reconcile")
    assert consumed(owner, computer_id)["status"] == "supported"
    before = current_obligation_state(owner)
    assert before["obligation_status"] == "active"
    assert before["proposal"]["status"] == "proposed"

    rpc(
        owner,
        computer_id,
        "reconcile-correct-dial",
        "invoke",
        correction_request("reconcile", task(owner)["current"]["Program"]["dial"]),
    )

    assert consumed(owner, computer_id)["status"] == "supported"
    after = current_obligation_state(owner)
    proposal = after["proposal"]
    assert after["obligation_status"] == "invalidated"
    assert after["obligation_version"] > before["obligation_version"]
    assert proposal["obligation"] == after["obligation_ref"]
    assert proposal["status"] == "invalidated"
    phase = proposal["phases"][-1]
    assert phase["phase"] == "invalidated"
    assert phase["proposal_status"] == "invalidated"
    assert phase["metadata"]["reason"] == "obligation-became-inactive"
    assert phase["metadata"]["invalidating_record"] == after["obligation_ref"]
    assert task(owner)["current"]["Program"]["dial"]["content_version"] == 2

    digest = task_sha256(owner)
    owner.close()
    reopened = FieldIntelligenceOwner(tmp_path / "reconcile")
    try:
        assert task_sha256(reopened) == digest
    finally:
        reopened.close()


def test_revision_without_reconciliation_strands_the_proposal(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        cassi_field_cognition,
        "_semantic_reanchor_action_proposal",
        lambda *args, **kwargs: None,
    )
    owner, computer_id = pausing_inquiry(tmp_path, "stranded")
    try:
        assert consumed(owner, computer_id)["status"] == "supported"
        before = task_sha256(owner)
        with pytest.raises(FieldIntelligenceError) as refusal:
            rpc(
                owner,
                computer_id,
                "stranded-correct-dial",
                "invoke",
                correction_request(
                    "stranded", task(owner)["current"]["Program"]["dial"]
                ),
            )
        assert refusal.value.code == "INVALID_SEMANTIC_REFERENCE"
        assert task_sha256(owner) == before
    finally:
        owner.close()
