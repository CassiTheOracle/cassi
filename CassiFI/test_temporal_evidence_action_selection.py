"""Focused contract checks for the temporal/evidence action-selection triple."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_temporal_evidence_action_selection.py"
VERIFIER = HERE / "verify_temporal_evidence_action_selection.py"
SCHEMA = "cassifi.temporal-evidence-action-selection.v1"


@pytest.fixture(scope="module")
def fresh_receipt(tmp_path_factory: pytest.TempPathFactory) -> dict:
    output = tmp_path_factory.mktemp("temporal-evidence") / "receipt.json"
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(output)],
        cwd=HERE,
        check=True,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert completed.stdout
    return json.loads(output.read_text(encoding="utf-8"))


def test_receipt_contract_and_controls(fresh_receipt: dict) -> None:
    assert fresh_receipt["schema"] == SCHEMA
    assert fresh_receipt["status"] == "MEASURED"
    assert fresh_receipt["numeric_policy"] == {"dtype": "float64", "device": "cpu", "seed": 20260917}
    assert fresh_receipt["held_out"]["declared"] is True
    assert fresh_receipt["held_out"]["kind"] == "presentation-permutation"
    assert len(fresh_receipt["rows"]) == 6
    assert fresh_receipt["evaluation"] == {
        "field_supported_selection": True,
        "held_out_consequence": True,
        "presentation_order_invariant": True,
        "no_workspace_abstains": True,
        "insufficient_margin_abstains": True,
        "forbidden_operation_abstains": True,
        "wrong_action_consequence_fails": True,
    }
    assert fresh_receipt["controls"]["read_only"]["all_rows"] is True

    supported, permuted = fresh_receipt["rows"][:2]
    assert supported["selection"]["reason"] == "resonant-compatibility"
    assert supported["selection"]["selection_margin"] > supported["minimum_margin"]
    assert supported["selection"]["selected"] == permuted["selection"]["selected"]
    assert supported["selection"]["candidate_set_sha256"] == permuted["selection"]["candidate_set_sha256"]
    assert supported["presentation_order_sha256"] != permuted["presentation_order_sha256"]
    consequence = supported["consequence"]
    assert consequence["expected_goal_observation"] == consequence["observation"]
    assert consequence["selected_action"] == consequence["action_applied"]
    assert consequence["correct_first_transition"] is True
    assert consequence["forbidden_outcome"] is False
    assert consequence["transition"]["receipt"]["action"] == consequence["action_applied"]
    assert consequence["transition"]["receipt"]["observation"] == consequence["observation"]
    no_workspace = fresh_receipt["rows"][2]
    assert no_workspace["field_setup"]["available"] is False
    assert no_workspace["selection"]["reason"] == "resonant-workspace-unavailable"
    assert no_workspace["selection"]["selected"] is None


def test_independent_verifier_rebuilds_receipt(fresh_receipt: dict, tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    receipt_path.write_text(json.dumps(fresh_receipt), encoding="utf-8")
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), "--receipt", str(receipt_path)],
        cwd=HERE,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "verified"
    assert result["content_digest"] == fresh_receipt["content_digest"]
    assert result["checks"]["mutation_anchor_fires"] is True
    assert result["checks"]["wrong_goal_anchor_fires"] is True
    assert result["checks"]["control_anchors_fire"] is True
