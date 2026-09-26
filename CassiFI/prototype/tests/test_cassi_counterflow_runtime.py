from __future__ import annotations

import hashlib
import json
from typing import Any

import pytest

from cassi_counterflow_runtime import DerivedCounterflowRuntime
from cassi_qi_field import QiFieldError


PRIMARY_SHA256 = "a" * 64


def _refresh_address(identity: dict[str, Any]) -> None:
    encoded = json.dumps(
        [
            "cassicore.mnemic.counterflow-address.v1",
            identity["record_id"],
            identity["revision"],
            identity["start_byte"],
            identity["end_byte"],
            identity["semantic_kind"],
        ],
        separators=(",", ":"),
    ).encode()
    identity["address"] = hashlib.sha256(encoded).digest()[:16].hex()


def _identity(label: str, position: int) -> dict[str, Any]:
    result = {
        "record_id": f"record:{label}",
        "revision": hashlib.sha256(f"revision:{label}".encode()).hexdigest(),
        "start_byte": position * 16,
        "end_byte": position * 16 + len(label.encode()),
        "semantic_kind": "field-transition",
    }
    _refresh_address(result)
    return result


def _request() -> dict[str, Any]:
    identities = [_identity(f"state-{position}", position) for position in range(4)]
    observations = [
        {
            "id": f"observed-{position}",
            "before": identities[position],
            "after": identities[position + 1],
            "symbol": f"op-{position}",
            "action": {
                "id": f"apply-op-{position}",
                "kind": "field-transition",
                "required_authority": 1.0,
                "reversible": True,
            },
        }
        for position in range(3)
    ]
    return {
        "mode": "plan",
        "observations": observations,
        "trajectory": [
            {
                **identity,
                "mask": [1.0, 1.0, 1.0, 1.0],
                "authority": 1.0,
                "required": True,
            }
            for identity in identities
        ],
        "policy": {
            "eligible_observation_ids": [item["id"] for item in observations],
            "permitted_action_kinds": ["field-transition"],
            "authority": 1.0,
            "authorization_path": ["thalamus:reasoning", "owner:execute-separately"],
        },
        "consolidate_macro": True,
    }


def _prediction_request(*, observed_outcome: str | None = None) -> dict[str, Any]:
    before = _identity("pending", 0)
    after = _identity("completed", 1)
    request: dict[str, Any] = {
        "mode": "predict",
        "observations": [
            {
                "id": "successful-action-1",
                "before": before,
                "after": after,
                "symbol": "tool:read",
                "outcome": "completed",
                "action": {
                    "id": "tool-signature",
                    "kind": "tool:read",
                    "required_authority": 1.0,
                    "reversible": False,
                    "effects": [
                        {
                            "record_id": "memory-effect",
                            "before_revision": "1" * 64,
                            "after_revision": "2" * 64,
                            "semantic_kind": "mnemic:update",
                            "start_byte": 0,
                            "end_byte": 5,
                        }
                    ],
                },
            }
        ],
        "current": before,
        "expected": after,
        "policy": {
            "eligible_observation_ids": ["successful-action-1"],
            "permitted_action_kinds": ["tool:read"],
            "authority": 1.0,
            "authorization_path": ["thalamus:plan", "omp:tool-call"],
        },
    }
    if observed_outcome is not None:
        request["observed_outcome"] = observed_outcome
    return request


def test_no_transition_data_is_advisory_and_nonpersistent() -> None:
    result = DerivedCounterflowRuntime().plan(
        {"mode": "plan", "observations": [], "trajectory": [], "policy": {}},
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result == {
        "schema": "cassi.counterflow.derived-runtime.v2",
        "schema_version": 2,
        "mode": "plan",
        "status": "no_transition_data",
        "derived": True,
        "persistent_state": False,
        "primary_field_sha256": PRIMARY_SHA256,
        "observation_count": 0,
        "plan": None,
        "prediction": None,
        "evaluation": None,
        "symbolic": None,
        "action_proposal": None,
        "macro": None,
        "abstention": {
            "code": "no_transition_data",
            "evidence": {"observation_count": 0},
        },
    }


def test_observed_mnemic_trajectory_settles_symbols_actions_and_ephemeral_macro() -> None:
    result = DerivedCounterflowRuntime().plan(
        _request(),
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "settled"
    assert result["derived"] is True
    assert result["persistent_state"] is False
    assert result["primary_field_sha256"] == PRIMARY_SHA256
    assert result["observation_count"] == 3
    assert len(result["training"]) == 3
    assert json.loads(json.dumps(result, allow_nan=False))["training"][0][
        "best_residual"
    ] is None
    assert result["plan"]["winning_observation_ids"] == [
        ["observed-0"],
        ["observed-1"],
        ["observed-2"],
    ]
    assert result["symbolic"]["symbols"] == ["op-0", "op-1", "op-2"]
    assert result["symbolic"]["source_record_ids"] == [
        "record:state-0",
        "record:state-1",
        "record:state-2",
        "record:state-3",
    ]
    assert result["action_proposal"] == {
        "inert": True,
        "basin_path": [0, 1, 2],
        "action_ids": ["apply-op-0", "apply-op-1", "apply-op-2"],
        "authorization_path": ["thalamus:reasoning", "owner:execute-separately"],
        "field_sha256": result["action_proposal"]["field_sha256"],
    }
    assert len(result["action_proposal"]["field_sha256"]) == 64
    assert result["macro"]["constituents"] == [0, 1, 2]
    assert result["macro"]["persisted"] is False
    assert result["inference_memory_frozen"] is True



def test_plan_leaves_zero_masked_intermediate_slots_unresolved() -> None:
    request = _request()
    for slot in request["trajectory"][1:-1]:
        slot["mask"] = [0.0, 0.0, 0.0, 0.0]
        slot["required"] = False

    result = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "settled"
    assert result["action_proposal"]["action_ids"] == [
        "apply-op-0",
        "apply-op-1",
        "apply-op-2",
    ]

def test_empty_exact_span_is_a_real_observation() -> None:
    request = _request()
    request["observations"][0]["before"]["end_byte"] = 0
    request["trajectory"][0]["end_byte"] = 0
    _refresh_address(request["observations"][0]["before"])
    _refresh_address(request["trajectory"][0])

    result = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "settled"
    assert result["symbolic"]["symbols"] == ["op-0", "op-1", "op-2"]


def test_held_out_prediction_is_field_only_target_blind_and_inert() -> None:
    runtime = DerivedCounterflowRuntime()
    request = _prediction_request()
    first = runtime.plan(request, primary_field_sha256=PRIMARY_SHA256)
    alternate = _prediction_request()
    alternate["expected"] = _identity("different-held-out-effect", 2)
    second = runtime.plan(alternate, primary_field_sha256=PRIMARY_SHA256)

    assert first["status"] == "predicted"
    assert first["prediction"] == second["prediction"]
    assert first["prediction"]["exact_effect"] == request["expected"]
    assert first["evaluation"]["prediction_residual"] is not None
    assert first["evaluation"]["identity_baseline_residual"] is not None
    assert first["inference_memory_frozen"] is True
    assert first["action_proposal"]["inert"] is True
    assert first["action_proposal"]["action_ids"] == ["tool-signature"]
    assert first["action_proposal"]["effects"] == request["observations"][0]["action"]["effects"]
    assert first["abstention"] is None



def test_ambiguous_prediction_serializes_diagnostics_without_action() -> None:
    request = _prediction_request()
    alternate = json.loads(json.dumps(request["observations"][0]))
    alternate["id"] = "successful-action-2"
    alternate["after"] = _identity("alternate-completed", 2)
    alternate["action"]["id"] = "tool-signature-2"
    request["observations"].append(alternate)
    request["policy"]["eligible_observation_ids"].append(alternate["id"])

    result = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "ambiguous"
    assert result["prediction"]["basin_id"] is None
    assert result["prediction"]["value"] is None
    assert result["prediction"]["margin"] <= 1.0e-3
    assert len(result["prediction"]["field_sha256"]) == 64
    assert result["inference_memory_frozen"] is True
    assert result["action_proposal"] is None
    assert result["abstention"]["code"] == "ambiguous_prediction"
    assert json.loads(json.dumps(result, allow_nan=False)) == result

def test_failed_action_outcome_is_measured_but_never_proposed() -> None:
    result = DerivedCounterflowRuntime().plan(
        _prediction_request(observed_outcome="error"),
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "predicted"
    assert result["evaluation"]["observed_outcome"] == "error"
    assert result["action_proposal"] is None
    assert result["abstention"]["code"] == "observed_action_error"


def test_default_off_failure_inhibition_uses_the_winning_field_basin() -> None:
    request = _prediction_request()
    request["observations"][0]["outcome"] = "error"
    without_inhibition = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )
    request["failure_inhibition"] = True
    inhibited = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert without_inhibition["action_proposal"]["inert"] is True
    assert inhibited["action_proposal"] is None
    assert inhibited["abstention"]["code"] == "failure_inhibited"
    assert inhibited["inhibition"] == {
        "enabled": True,
        "failure_support": 1,
        "success_support": 0,
        "inhibited": True,
    }


def test_prediction_abstains_with_exact_authority_evidence() -> None:
    request = _prediction_request()
    request["policy"]["authority"] = 0.5
    result = DerivedCounterflowRuntime().plan(
        request,
        primary_field_sha256=PRIMARY_SHA256,
    )

    assert result["status"] == "predicted"
    assert result["action_proposal"] is None
    assert result["abstention"]["code"] == "insufficient_authority"

def test_request_rejects_forged_provenance_and_insufficient_authority() -> None:
    forged = _request()
    forged["observations"][0]["before"]["record_id"] = "different-record"
    with pytest.raises(QiFieldError, match="exact record provenance"):
        DerivedCounterflowRuntime().plan(
            forged,
            primary_field_sha256=PRIMARY_SHA256,
        )

    unauthorized = _request()
    unauthorized["policy"]["authority"] = 0.5
    with pytest.raises(QiFieldError, match="authority is insufficient"):
        DerivedCounterflowRuntime().plan(
            unauthorized,
            primary_field_sha256=PRIMARY_SHA256,
        )
