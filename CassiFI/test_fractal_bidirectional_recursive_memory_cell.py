from __future__ import annotations

import json
from pathlib import Path

import pytest

import cassi_resonant_field as field
import run_fractal_bidirectional_recursive_memory_cell as runner

RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _persisted_receipt() -> dict:
    assert RECEIPT.is_file(), (
        f"Missing receipt {RECEIPT}; run `python {Path(runner.__file__).name} "
        f"--output {runner.DEFAULT_OUTPUT.as_posix()}` from CassiFI."
    )
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    return receipt


def test_live_child_detail_to_parent_receipt_is_self_consistent() -> None:
    receipt = runner.build_receipt()
    persisted = _persisted_receipt()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_LIVE_CHILD_DETAIL_TO_PARENT"
    assert persisted["verdict"] == receipt["verdict"]
    assert persisted["content_digest"] == receipt["content_digest"]
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    assert all(row["holds"] for row in receipt["comparisons"])
    assert receipt["arms"]["parent-on"]["application"]["accepted"]
    assert not receipt["arms"]["parent-off"]["application"]["accepted"]
    assert receipt["controls"]["frozen_lock"]["can_fail"]
    assert receipt["controls"]["stale_source"]["can_fail"]
    assert receipt["controls"]["stale_packet"]["can_fail"]
    assert receipt["controls"]["stale_relation"]["can_fail"]
    assert receipt["controls"]["tampered_relation"]["can_fail"]
    assert receipt["controls"]["owner"]["replay_same_state"]
    assert receipt["declared"]["semantic_memory_claim"] is False


def test_live_child_detail_transition_rejects_frozen_parent() -> None:
    origin = field.initial_workspace(field.ResonantProfile())
    captured, _ = field.write_parent_registers(
        origin, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, _ = field.freeze_parent(captured)
    with pytest.raises(field.ResonantNumericalError, match="locked"):
        field.apply_live_child_detail_to_parent(frozen, work_budget=runner.FEEDBACK_BUDGET)
