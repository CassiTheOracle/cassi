from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import run_fractal_multicycle_recursive_memory_cell as runner

RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _persisted() -> dict:
    assert RECEIPT.is_file(), (
        f"Missing receipt {RECEIPT}; run `python {Path(runner.__file__).name} "
        f"--output {runner.DEFAULT_OUTPUT.as_posix()}` from CassiFI."
    )
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    return receipt


def test_bounded_multicycle_primary_observable_and_controls() -> None:
    receipt = runner.build_receipt()
    persisted = _persisted()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE"
    assert persisted["verdict"] == receipt["verdict"]
    assert persisted["content_digest"] == receipt["content_digest"]
    assert len(receipt["arms"]["feedback-on"]["cycles"]) == 3
    assert len(receipt["arms"]["feedback-off"]["cycles"]) == 3
    assert receipt["arms"]["feedback-on"]["upward_enabled"] is True
    assert receipt["arms"]["feedback-off"]["upward_enabled"] is False
    assert receipt["arms"]["feedback-on"]["parent_enabled"] is True
    assert receipt["arms"]["feedback-off"]["parent_enabled"] is True
    contrast = receipt["later_child_contrast"]
    assert contrast["field_state_delta_norm"] > runner.MARGIN
    assert contrast["effective_flow_delta_norm"] > runner.MARGIN
    assert contrast["packet_delta_norm"] > runner.MARGIN
    assert contrast["persistence_ratio"] > runner.MARGIN
    assert contrast["selectivity_ratio"] <= runner.MARGIN
    assert receipt["arms"]["feedback-on"]["child_state_sha256s"][0] == receipt["arms"]["feedback-off"]["child_state_sha256s"][0]
    assert receipt["arms"]["feedback-on"]["child_state_sha256s"][2] != receipt["arms"]["feedback-off"]["child_state_sha256s"][2]
    for name in ("feedback-on", "feedback-off", "parent-off"):
        for row in receipt["arms"][name]["cycles"]:
            assert row["downward"]["component"] == "detail"
            assert row["downward"]["child_path"] == "LL"
            assert row["downward_target_packet_delta_norm"] > runner.MARGIN
            assert row["downward_target_field_state_delta_norm"] > runner.MARGIN
            assert row["sibling_delta_norm"] <= runner.MARGIN
        assert receipt["arms"][name]["cycles"][-1]["release"].get("released") is True
    for row in receipt["arms"]["zero-work"]["cycles"]:
        assert row["downward_target_packet_delta_norm"] == 0.0
        assert row["downward_target_field_state_delta_norm"] == 0.0
        assert row["release"].get("released") is True
        assert row["sibling_delta_norm"] == 0.0
    assert all(row["parent_register_preserved_before_materialize"] for arm in receipt["arms"].values() for row in arm["cycles"][:-1])
    assert receipt["controls"]["standalone_upward_zero_work"]["can_fail"]
    assert receipt["controls"]["immutable_roundtrip"]["can_fail"]
    assert receipt["controls"]["persistence_selectivity_mutation"]["can_fail"]


def test_independent_verifier_rebuilds_published_receipt() -> None:
    _persisted()
    verifier = Path(__file__).resolve().with_name("verify_fractal_multicycle_recursive_memory_cell.py")
    completed = subprocess.run(
        [sys.executable, str(verifier), "--receipt", str(RECEIPT)],
        cwd=RECEIPT.parent,
        check=True,
        capture_output=True,
        text=True,
    )
    result = json.loads(completed.stdout.strip())
    assert result["status"] == "verified"
    assert result["verdict"] == "PASS_FIELD_OWNED_BOUNDED_MULTICYCLE_UPWARD_RECURRENCE"
    assert result["digest"] == _persisted()["content_digest"]
