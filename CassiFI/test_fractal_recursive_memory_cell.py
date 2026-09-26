from __future__ import annotations

import json
from pathlib import Path

import cassi_resonant_field as field
import run_fractal_recursive_memory_cell as runner

RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _persisted_receipt() -> dict:
    assert RECEIPT.is_file(), (
        f"Missing receipt {RECEIPT}; run `python {Path(runner.__file__).name} "
        f"--output {runner.DEFAULT_OUTPUT.as_posix()}` from CassiFI."
    )
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    return receipt


def test_closed_two_cycle_primary_later_child_observable() -> None:
    receipt = runner.build_receipt()
    persisted = _persisted_receipt()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_CLOSED_TWO_CYCLE_ACTIVE_UPWARD_RECURRENCE"
    assert persisted["verdict"] == receipt["verdict"]
    assert persisted["content_digest"] == receipt["content_digest"]
    assert runner.verify_receipt(receipt)["content_digest_matches"]
    assert all(row["holds"] for row in receipt["comparisons"])
    contrast = receipt["later_child_contrast"]
    assert contrast["field_state_delta_norm"] > runner.MARGIN
    assert contrast["effective_flow_delta_norm"] > runner.MARGIN
    assert contrast["packet_delta_norm"] > runner.MARGIN
    assert receipt["arms"]["full-loop"]["later_application"]["parent_enabled"]
    assert not receipt["arms"]["feedback-off"]["later_application"]["parent_enabled"]
    assert not receipt["arms"]["parent-off"]["first_application"]["parent_enabled"]
    assert receipt["source_off"]["source_enabled"] is False
    assert receipt["controls"]["stale_recompute"]["can_fail"]
    assert receipt["controls"]["stale_upward_source"]["can_fail"]
    assert receipt["controls"]["stale_upward_packet"]["can_fail"]
    assert receipt["controls"]["stale_upward_relation"]["can_fail"]
    assert receipt["arms"]["full-loop"]["first_application"]["component"] == "detail"
    assert receipt["arms"]["full-loop"]["later_application"]["component"] == "detail"
    assert receipt["arms"]["full-loop"]["upward_application"]["accepted"]
    assert receipt["arms"]["full-loop"]["parent_register_preserved_before_materialize"]
    assert receipt["arms"]["full-loop"]["materialize_parent"]["schema"] == "cassifi.parent-child-summary-recompute.v1"
    assert receipt["controls"]["stale_parent"]["can_fail"]
    assert receipt["controls"]["tampered_relation"]["can_fail"]
    assert receipt["controls"]["owner"]["replay_same_state"]
    assert receipt["declared"]["semantic_memory_claim"] is False
    assert receipt["declared"]["task_utility_claim"] is False


def test_updated_parent_reaches_later_child_not_just_register() -> None:
    receipt = runner.build_receipt()
    full = receipt["arms"]["full-loop"]
    feedback_off = receipt["arms"]["feedback-off"]
    assert full["later_child_final_state_sha256"] != feedback_off["later_child_final_state_sha256"]
    assert full["later_child_flow_signal"] != feedback_off["later_child_flow_signal"]


def test_frozen_parent_route_remains_locked_until_release() -> None:
    origin = field.initial_workspace(field.ResonantProfile())
    seeded, _ = field.apply_helical_packet_impulse(
        origin,
        path="LL",
        component="scale",
        flow_signal=runner.SEED_FLOW,
        work_budget=runner.SEED_BUDGET,
        evidence_tick=origin.evidence_tick,
        event_kind="reasoning-work",
    )
    captured, _ = field.write_parent_registers(
        seeded, paths=("L", "LL"), ancestry_pairs=(("L", "LL"),)
    )
    frozen, freeze = field.freeze_parent(captured)
    try:
        field.recompute_parent_summary_from_child(frozen)
    except field.ResonantNumericalError as exc:
        assert "locked" in str(exc)
    else:
        raise AssertionError("recompute unexpectedly accepted while frozen parent was active")
    assert freeze["accepted"]
