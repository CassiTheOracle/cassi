"""Focused checks for the field-only hierarchical memory probe receipt."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_hierarchical_memory_exploration as runner


RECEIPT = Path(__file__).resolve().parent / runner.DEFAULT_OUTPUT


def _receipt() -> dict:
    assert RECEIPT.is_file(), f"missing receipt: {RECEIPT}"
    value = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert runner.verify_receipt(value)["content_digest_matches"]
    return value


def test_digest_and_mutation_control() -> None:
    receipt = _receipt()
    assert receipt["verdict"] == "PASS_FIELD_ONLY_HIERARCHICAL_MEMORY_PROBE"
    mutated = copy.deepcopy(receipt)
    mutated["arms"]["current-meaningful-helix"]["comparison"]["parent_difference"] += 0.25
    assert runner.content_digest(mutated) != receipt["content_digest"]
    assert receipt["controls"]["all_firing"] is True


def test_three_arrangements_have_real_owner_consolidation_and_controls() -> None:
    receipt = _receipt()
    assert {item["label"] for item in receipt["declared"]["arrangements"]} == {
        "current-meaningful-helix",
        "core-shell-loops",
        "nested-paired-loops",
    }
    for label, arm in receipt["arms"].items():
        consolidated = arm["consolidated"]
        no_consolidation = arm["no_consolidation"]
        silenced = arm["silenced"]
        assert consolidated["child_write"]["accepted"] is True
        assert consolidated["parent_consolidation"]["schema"] == "cassifi.parent-child-summary-recompute.v1"
        assert consolidated["parent_consolidation"]["parent_path"] == "L"
        assert consolidated["parent_consolidation"]["child_path"] == "LL"
        assert consolidated["mutation_control"]["attempted"]
        assert consolidated["mutation_control"]["can_fail"]
        assert consolidated["mutation_control"]["expected_code_matches"]
        assert no_consolidation["child_write"]["accepted"] is True
        assert no_consolidation["parent_consolidation"] is None
        assert silenced["child_write"] is None
        assert silenced["parent_consolidation"] is None
        assert arm["comparison"]["rows"]


def test_field_only_recovery_observable_separates_controls() -> None:
    receipt = _receipt()
    for arm in receipt["arms"].values():
        consolidated = arm["consolidated"]["field_only_observable"]
        no_consolidation = arm["no_consolidation"]["field_only_observable"]
        silenced = arm["silenced"]["field_only_observable"]
        assert consolidated["recovery_after_source_off"] > runner.MARGIN
        assert consolidated["cue_cosine_sq_after_source_off"] > 0.0
        assert consolidated["parent_survival_drift_l2"] <= runner.MARGIN
        assert consolidated["child_source_off_change_l2"] > runner.MARGIN
        assert no_consolidation["recovery_after_source_off"] <= runner.MARGIN
        assert silenced["recovery_after_source_off"] <= runner.MARGIN
        assert arm["comparison"]["parent_difference"] > runner.MARGIN
        assert abs(arm["comparison"]["recovery_difference"]) > runner.MARGIN
        assert all(row["holds"] for row in arm["comparison"]["rows"])
        assert all(not row["firing_control"]["holds_after_mutation"] for row in arm["comparison"]["rows"])


def test_lineage_source_off_and_continuity() -> None:
    receipt = _receipt()
    for arm in receipt["arms"].values():
        consolidated = arm["consolidated"]
        relation = consolidated["relation_before"]
        recompute = consolidated["parent_consolidation"]
        after_off = consolidated["reads"]["after_source_off"]
        assert relation["parent_path"] == "L"
        assert relation["child_path"] == "LL"
        assert recompute["previous_relation_sha256"] == relation["relation_sha256"]
        assert recompute["relation_sha256"] != relation["relation_sha256"]
        assert after_off["stored_parent"]["present"] is True
        assert consolidated["source_off"]["source_enabled"] is False
    checks = receipt["continuity_checks"]
    assert len(checks) >= 2
    assert all(row["within_tolerance"] for row in checks)


def test_rebuild_is_content_deterministic() -> None:
    receipt = _receipt()
    rebuilt = runner.build_receipt()
    assert rebuilt["content_digest"] == receipt["content_digest"]
    assert runner.content_digest(rebuilt) == rebuilt["content_digest"]
    assert rebuilt["runtime_seconds"] < 180.0
