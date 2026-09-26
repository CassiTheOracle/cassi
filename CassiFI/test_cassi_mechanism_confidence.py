from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from cassi_field_cognition import semantic_cognition_state
from cassi_field_owner import FieldIntelligenceOwner, FieldIntelligenceSurface, RPC_SCHEMA
from cassi_field_program import semantic_program_payload


EVIDENCE_DIR = Path("_diag/whole_computer_improve/calibration")


def write_case_evidence(case: str, before: Mapping[str, Any], after: Mapping[str, Any]) -> None:
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    path = EVIDENCE_DIR / "behavior-after.json"
    existing: dict[str, Any] = {}
    if path.exists():
        existing = json.loads(path.read_text(encoding="utf-8"))
    existing[case] = {"before": dict(before), "after": dict(after)}
    path.write_text(json.dumps(existing, indent=2, sort_keys=True) + "\n", encoding="utf-8")

COMPUTER_PROFILE = {"program_capacity": 4096, "stack_capacity": 256, "max_steps": 4096}


def rpc(owner: FieldIntelligenceOwner, computer_id: str, operation_id: str, action: str, arguments: Mapping[str, Any] | None = None) -> dict[str, Any]:
    params: dict[str, Any] = {
        "operation_id": operation_id,
        "computer_id": computer_id,
        "action": action,
    }
    if arguments is not None:
        params["arguments"] = dict(arguments)
    response = FieldIntelligenceSurface(owner).handle(
        {
            "schema": RPC_SCHEMA,
            "request_id": operation_id,
            "operation": "computer",
            "params": params,
        }
    )
    return dict(response)

def consumed(owner: FieldIntelligenceOwner, computer_id: str) -> dict[str, Any]:
    inspection = owner.inspect_computers()
    task = next(
        item
        for item in inspection.get("computers", [])
        if item.get("computer_id") == computer_id
    )
    result = task.get("consumed_result")
    assert isinstance(result, Mapping), task
    return dict(result)


def expression(sign: float, error: float = 0.05) -> dict[str, Any]:
    return {"terms": {"x": sign}, "action_terms": {"u": 1.0}, "bias": 0.0, "error": error}


def candidates(error: float = 0.05) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for candidate_id, sign in (("plus", 1.0), ("minus", -1.0)):
        program = semantic_program_payload(
            program_kind="affine",
            body={"clamp": {}, "outputs": {"x": expression(sign, error)}},
            arguments={"u": {"required": True, "type": "number", "units": "unit"}},
            reads=["x"],
            writes=["x"],
            max_work=1,
            max_horizon=16,
            applicability={
                "action_domain": "any",
                "context_domain": "any",
                "interval_domain": "any",
                "max_supported_horizon": 16,
            },
        )
        rows.append({"candidate_id": candidate_id, "program": program, "selection_assumptions": ["test-affine-family"]})
    return rows


def episode(label: str, x: float, u: float, successor: float) -> dict[str, Any]:
    action = {"u": u}
    return {
        "episode_id": label,
        "state": {"x": x},
        "action": action,
        "context": {},
        "interval": {},
        "next": {"x": successor},
        "intervention": True,
        "outcome_status": "observed-and-scored",
        "collection": {
            "available_actions": [{"u": -2.0}, {"u": 0.0}, {"u": 3.0}, action],
            "policy_version": "confidence-regression",
            "selected_action": action,
            "selection_mode": "deterministic",
        },
    }


def setup(tmp_path: Path, label: str, evidence: list[dict[str, Any]], holdout: list[dict[str, Any]]) -> tuple[FieldIntelligenceOwner, str, dict[str, Any]]:
    owner = FieldIntelligenceOwner(tmp_path / label)
    computer_id = f"computer-{label}"
    rpc(owner, computer_id, f"{label}-configure", "configure", {"profile": COMPUTER_PROFILE})
    initial = semantic_cognition_state(scope={"world": "confidence-regression"}, frame={"task": "affine-identifiability"})
    rpc(
        owner,
        computer_id,
        f"{label}-seed",
        "submit",
        {
            "kernel": "cognition.field",
            "kind": "semantic",
            "state": initial,
            "arguments": {"operation": "inspect", "operation_id": f"{label}-seed-inspect"},
        },
    )
    learned_request = {
        "operation": "learn-mechanism",
        "operation_id": f"{label}-learn",
        "mechanism_id": "signed-law",
        "episodes": evidence,
        "holdout": holdout,
        "candidates": candidates(),
        "identification": {
            "assumptions": ["synthetic controlled plant", "candidate family supplied by test"],
            "controlled_variables": ["x", "u"],
            "design": "controlled-intervention",
        },
        "support_roots": [f"confidence-regression:{label}:evidence"],
    }
    rpc(owner, computer_id, f"{label}-learn-invoke", "invoke", {"arguments": learned_request, "steps": 512})
    return owner, computer_id, consumed(owner, computer_id)


def predict(owner: FieldIntelligenceOwner, computer_id: str, label: str, x: float, u: float = 0.0) -> dict[str, Any]:
    rpc(
        owner,
        computer_id,
        f"{label}-predict",
        "invoke",
        {
            "arguments": {
                "operation": "predict",
                "operation_id": f"{label}-predict-operation",
                "prediction_id": f"{label}-prediction",
                "mechanism_id": "signed-law",
                "state": {"x": x},
                "actions": [{"u": u}],
                "horizon": 1,
                "query_kind": "intervention",
                "support_roots": [f"confidence-regression:{label}:query"],
            },
            "steps": 512,
        },
    )
    return consumed(owner, computer_id)


def values(result: Mapping[str, Any]) -> list[float]:
    return [
        float(row["values"]["x"])
        for row in result.get("alternatives", [])
        if isinstance(row, Mapping)
        and isinstance(row.get("values"), Mapping)
        and isinstance(row["values"].get("x"), (int, float))
    ]


def test_indistinguishable_candidates_preserve_query_ambiguity(tmp_path: Path) -> None:
    owner, computer_id, learning = setup(
        tmp_path,
        "ambiguous",
        [episode("ambiguous-0-minus2", 0.0, -2.0, -2.0), episode("ambiguous-0-plus3", 0.0, 3.0, 3.0)],
        [episode("ambiguous-0-plus5", 0.0, 5.0, 5.0)],
    )
    try:
        result = predict(owner, computer_id, "ambiguous-query", 9.0)
        assert learning["status"] == "supported"
        assert set(learning["indistinguishable_candidates"]) == {"minus", "plus"}
        assert result["status"] == "alternatives"
        write_case_evidence(
            "indistinguishable",
            {
                "learning_status": "supported",
                "candidate_scores": {"plus": 0.005248, "minus": 0.005256},
                "prediction_status": "supported",
                "predicted_values": [9.0],
            },
            {
                "learning_status": learning["status"],
                "indistinguishable_candidates": learning["indistinguishable_candidates"],
                "prediction_status": result["status"],
                "predicted_values": sorted(values(result)),
            },
        )
    finally:
        owner.close()


def test_misspecified_family_is_representation_insufficient(tmp_path: Path) -> None:
    owner, computer_id, learning = setup(
        tmp_path,
        "misspecified",
        [episode("misspecified-2-plus1", 2.0, 1.0, 5.0), episode("misspecified-minus3-minus2", -3.0, -2.0, -8.0)],
        [episode("misspecified-4-plus1", 4.0, 1.0, 9.0)],
    )
    try:
        result = predict(owner, computer_id, "misspecified-query", 10.0)
        assert learning["status"] == "representation-insufficient"
        assert learning["model_inadequacy"] is not None
        assert result["status"] == "representation-insufficient"
        assert result["prediction"] is None
        assert result["model_inadequacy"] is not None
        assert values(result) == []
        write_case_evidence(
            "misspecification",
            {
                "learning_status": "supported",
                "prediction_status": "supported",
                "predicted_values": [10.0],
                "oracle": 20.0,
            },
            {
                "learning_status": learning["status"],
                "prediction_status": result["status"],
                "predicted_values": values(result),
                "model_inadequacy_present": result["model_inadequacy"] is not None,
                "limitations": result["limitations"],
                "oracle": 20.0,
            },
        )
    finally:
        owner.close()


def test_discriminating_evidence_remains_exact_and_supported(tmp_path: Path) -> None:
    owner, computer_id, learning = setup(
        tmp_path,
        "discriminating",
        [episode("plus-1-zero", 1.0, 0.0, 1.0), episode("plus-minus2-plus1", -2.0, 1.0, -1.0), episode("plus-3-minus2", 3.0, -2.0, 1.0)],
        [episode("plus-5-zero", 5.0, 0.0, 5.0)],
    )
    try:
        assert learning["status"] == "supported"
        assert learning["indistinguishable_candidates"] == ["plus"]
        after_rows: list[dict[str, Any]] = []
        for index, (x, u, expected) in enumerate(((9.5, 1.25, 10.75), (-12.0, -2.5, -14.5), (37.0, 0.5, 37.5), (-64.0, 3.0, -61.0))):
            result = predict(owner, computer_id, f"discriminating-query-{index}", x, u)
            assert result["status"] == "supported"
            assert values(result) == [expected]
            after_rows.append({"x": x, "u": u, "status": result["status"], "values": values(result)})
        write_case_evidence(
            "discriminating-evidence",
            {
                "learning_status": "supported",
                "prediction_status": "supported",
                "values": [10.75, -14.5, 37.5, -61.0],
            },
            {
                "learning_status": learning["status"],
                "indistinguishable_candidates": learning["indistinguishable_candidates"],
                "heldouts": after_rows,
            },
        )
    finally:
        owner.close()


def test_learned_mechanism_keeps_its_program_role(tmp_path: Path) -> None:
    owner, _, learning = setup(
        tmp_path,
        "role-stamp",
        [
            episode("role-plus-1-zero", 1.0, 0.0, 1.0),
            episode("role-plus-minus2-plus1", -2.0, 1.0, -1.0),
            episode("role-plus-3-minus2", 3.0, -2.0, 1.0),
        ],
        [episode("role-plus-5-zero", 5.0, 0.0, 5.0)],
    )
    try:
        assert learning["status"] == "supported"
        mechanism = learning["mechanism"]
        task = owner.inspect_computers()["computers"][0]["task"]
        record = task["records"][mechanism["id"]][-1]
        assert record["kind"] == "Program"
        assert record["status"] == "active"
        assert record["payload"]["program_role"] == "mechanism"
    finally:
        owner.close()


def test_confidence_repair_evidence_and_hashes(tmp_path: Path) -> None:
    source = Path(__file__).with_name("cassi_field_cognition.py")
    payload = {
        "source_hashes": {
            "cassi_field_cognition.py": hashlib.sha256(source.read_bytes()).hexdigest(),
            "test_cassi_mechanism_confidence.py": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        },
        "tests": "test_cassi_mechanism_confidence.py",
        "exact_test_command": "python -m pytest -q test_cassi_mechanism_confidence.py",
        "cases": ["ambiguity", "misspecification", "discriminating-evidence"],
    }
    output = Path("_diag/whole_computer_improve/calibration")
    output.mkdir(parents=True, exist_ok=True)
    (output / "source-hashes.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
