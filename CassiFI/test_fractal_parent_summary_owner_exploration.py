"""Focused checks for the owner-level parent-summary exploration receipt."""
from __future__ import annotations

import json
from pathlib import Path

import run_fractal_parent_summary_owner_exploration as runner


RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _receipt() -> dict:
    assert RECEIPT.is_file(), f"Missing receipt {RECEIPT}; run the owner exploration runner first"
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(value)["content_digest_matches"]
    return value


def test_owner_transaction_reloads_and_replays() -> None:
    receipt = _receipt()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_PARENT_SUMMARY_OWNER_TRANSACTION"
    owner = receipt["owner"]
    assert owner["checkpoint_generation_after_parent"] == owner["checkpoint_generation_before_parent"] + 1
    assert owner["checkpoint_manifest_after_parent"] != owner["checkpoint_manifest_before_parent"]
    assert owner["logical_tick_after_parent"] == owner["logical_tick_before_parent"]
    assert owner["evidence_tick_after_parent"] == owner["evidence_tick_before_parent"]
    assert owner["reload_read"]["summary_sha256"] == owner["post_write_read"]["summary_sha256"]
    assert owner["replay"]["checkpoint_receipt"]["replayed"]
    assert owner["replay_state_unchanged"]
    assert owner["replay_manifest_unchanged"]


def test_owner_read_is_direct_and_retention_continuity_holds() -> None:
    receipt = _receipt()
    continuity = receipt["retention_continuity"]
    margins = receipt["declared"]["retention_continuity_margins"]
    assert continuity["summary_values_l2"] <= margins["summary_values_l2"]
    assert continuity["live_drift_absolute"] <= margins["live_drift_absolute"]
    assert continuity["owner_stored_summary_change_norm"] <= margins["stored_change_l2"]
    assert receipt["controls"]["read_analyzer_bypass"]["can_fail"]
    assert receipt["controls"]["read_analyzer_bypass"]["read_noop"]
    assert receipt["owner"]["read_only_state_unchanged"]


def test_owner_controls_fail_closed() -> None:
    receipt = _receipt()
    controls = receipt["controls"]
    stale = controls["stale_expected_state"]
    duplicate = controls["duplicate_active_summary"]
    corruption = controls["checkpoint_page_mutation"]
    assert stale["can_fail"] and stale["expected_code_matches"]
    assert stale["current_unchanged"]
    assert duplicate["can_fail"] and duplicate["expected_code_matches"]
    assert duplicate["current_unchanged"]
    assert corruption["can_fail"] and corruption["expected_code_matches"]
