"""Focused smoke tests for the unsupported-capability composition probe."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


HERE = Path(__file__).resolve().parent
RUNNER = HERE / "run_temporal_composition_probe.py"
VERIFIER = HERE / "verify_temporal_composition_probe.py"


def _run_probe(path: Path) -> dict:
    completed = subprocess.run(
        [sys.executable, str(RUNNER), "--output", str(path)],
        cwd=HERE, check=True, capture_output=True, text=True, timeout=90,
    )
    assert '"verdict": "UNSUPPORTED"' in completed.stdout
    return json.loads(path.read_text(encoding="utf-8"))


def test_public_composition_probe_reports_unresolved_unseen_order(tmp_path: Path) -> None:
    receipt = _run_probe(tmp_path / "receipt.json")
    assert receipt["schema"] == "cassifi.temporal-composition-probe.v1"
    assert receipt["verdict"] == "UNSUPPORTED"
    assert receipt["evaluation"]["held_out_composition_absent_from_training"] is True
    assert receipt["evaluation"]["second_primitive_selected_after_first"] is False
    assert receipt["evaluation"]["ordered_composition_supported"] is False
    assert receipt["evaluation"]["ordered_composition_unresolved"] is True
    assert receipt["evaluation"]["negative_denied_second_abstains"] is True


def test_independent_verifier_accepts_receipt_and_firing_anchors(tmp_path: Path) -> None:
    receipt_path = tmp_path / "receipt.json"
    _run_probe(receipt_path)
    completed = subprocess.run(
        [sys.executable, str(VERIFIER), "--receipt", str(receipt_path)],
        cwd=HERE, check=True, capture_output=True, text=True, timeout=30,
    )
    result = json.loads(completed.stdout)
    assert result["status"] == "verified"
    assert result["checks"]["digest"] is True
    assert result["checks"]["provenance_rebuilt"] is True
    assert result["checks"]["second_selection_anchor_fires"] is True
    assert result["checks"]["provenance_anchor_fires"] is True
    assert result["checks"]["negative_can_fail"] is True


def test_receipt_content_digest_is_clock_free(tmp_path: Path) -> None:
    first = _run_probe(tmp_path / "first.json")
    second = _run_probe(tmp_path / "second.json")
    assert first["content_digest"] == second["content_digest"]
    assert first["receipt_digest"] == second["receipt_digest"]
    assert first["timing"]["runtime_seconds"] != second["timing"]["runtime_seconds"]
