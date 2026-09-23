"""Focused tests for the bounded field-owned L/LL parent-child contract."""
from __future__ import annotations

import json
from pathlib import Path

import run_fractal_parent_child_contract as runner


RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _receipt() -> dict:
    assert RECEIPT.is_file(), "run the parent-child contract runner first"
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(value)["content_digest_matches"]
    return value


def test_child_change_requires_explicit_parent_recompute() -> None:
    receipt = _receipt()
    assert receipt["verdict"] == "PASS_FIELD_OWNED_PARENT_CHILD_CONTRACT"
    observables = receipt["observables"]
    assert observables["child_live_packet_changed"]
    assert observables["parent_unchanged_without_recompute_l2"] <= receipt["declared"]["margin"]
    assert observables["parent_changed_on_explicit_recompute_l2"] > receipt["declared"]["margin"]


def test_source_off_and_reload_preserve_recomputed_parent() -> None:
    receipt = _receipt()
    observables = receipt["observables"]
    assert observables["source_off_parent_drift_l2"] <= receipt["declared"]["margin"]
    assert observables["reload_parent_drift_l2"] <= receipt["declared"]["margin"]
    assert receipt["reload_read"]["read_only"] is True


def test_lineage_and_firing_controls() -> None:
    receipt = _receipt()
    assert receipt["lineage"]["parent_lineage_bound"]
    assert receipt["lineage"]["recomputed_relation_sha256"] != receipt["lineage"]["initial_relation_sha256"]
    rpc = receipt["surface_rpc"]
    assert rpc["operation"] == "recompute_parent_summary_from_child"
    assert rpc["ok"] is True
    assert rpc["request_schema"] == "cassifi.field-intelligence-request.v2"
    assert rpc["response_schema"] == "cassifi.field-intelligence-response.v2"
    assert rpc["result_lineage"]["relation_sha256"] == receipt["lineage"]["recomputed_relation_sha256"]
    for control in receipt["controls"].values():
        assert control["attempted"] and control["can_fail"]
        assert control["accepted"] is False
        assert control["expected_code_matches"]
