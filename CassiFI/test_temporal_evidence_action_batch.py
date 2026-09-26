"""Focused fresh-receipt checks for the concurrent temporal/evidence batch."""
from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import pytest
HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_temporal_evidence_action_batch.py"
VERIFIER = HERE / "verify_temporal_evidence_action_batch.py"
SCHEMA = "cassifi.temporal-evidence-action-batch.v1"
@pytest.fixture(scope="module")
def fresh_receipt(tmp_path_factory: pytest.TempPathFactory) -> dict:
    out = tmp_path_factory.mktemp("temporal-evidence-batch") / "receipt.json"
    p = subprocess.run([sys.executable, str(RUNNER), "--output", str(out), "--workers", "6"], cwd=HERE, check=True, capture_output=True, text=True, timeout=60)
    assert p.stdout and out.exists()
    return json.loads(out.read_text(encoding="utf-8"))
def test_concurrent_matrix_and_controls(fresh_receipt: dict) -> None:
    assert fresh_receipt["schema"] == SCHEMA
    assert fresh_receipt["status"] == "MEASURED"
    parallel = fresh_receipt["parallelism"]
    assert parallel["case_count"] >= 8
    assert parallel["requested_worker_count"] >= 4
    assert parallel["used_worker_count"] >= 4
    assert parallel["canonical_case_order"] == sorted(parallel["canonical_case_order"])
    assert len(fresh_receipt["rows"]) == parallel["case_count"]
    assert fresh_receipt["evaluation"] == {
        "field_supported_selection": True,
        "three_candidate_case": True,
        "multi_step_consequence": True,
        "held_out_composition_unsupported": True,
        "no_workspace_abstains": True,
        "insufficient_margin_abstains": True,
        "forbidden_operation_abstains": True,
        "infeasible_operation_abstains": True,
        "wrong_action_consequence_fails": True,
        "order_permutation_invariant": True,
    }
    rows = {r["name"]: r for r in fresh_receipt["rows"]}
    assert rows["three-candidate"]["selection"]["candidate_count"] >= 3
    assert len(rows["multi-step-consequence"]["transitions"]) >= 2
    unsupported = rows["unsupported-held-out-composition"]
    assert unsupported["selection"]["status"] == "unresolved"
    assert unsupported["expected_observed"] == {"expected": "unsupported", "observed": "unsupported", "match": True}
    assert unsupported["setup"]["held_out_source_digest_absent_from_training"] is True
    assert unsupported["setup"]["held_out_source_content_sha256"] not in unsupported["setup"]["training_source_content_sha256"]
    assert all(r["read_only"] and r["state_unchanged"] for r in fresh_receipt["rows"])
    assert rows["continuity-baseline"]["continuity_reproduction"]["baseline_selection_margin"] == 0.035448902588912756
    assert rows["continuity-baseline"]["continuity_reproduction"]["baseline_candidate_set_sha256"] == "74ce5086ef4ae6135f97b46549ffd68839a0d97c0d95e3815963a37345373b5d"
def test_independent_verifier_and_anchors(fresh_receipt: dict, tmp_path: Path) -> None:
    path = tmp_path / "receipt.json"; path.write_text(json.dumps(fresh_receipt), encoding="utf-8")
    p = subprocess.run([sys.executable, str(VERIFIER), "--receipt", str(path)], cwd=HERE, check=True, capture_output=True, text=True, timeout=10)
    result = json.loads(p.stdout)
    assert result["status"] == "verified"
    for key in ("selected_action_anchor_fires", "expected_goal_anchor_fires", "case_count_anchor_fires", "concurrency_anchor_fires", "control_anchor_fires", "held_out_scope_anchor_fires", "aggregates_rederived"):
        assert result["checks"][key] is True
