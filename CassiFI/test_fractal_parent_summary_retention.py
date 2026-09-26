"""Focused regression tests for the canonical Workspace parent-summary register."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

import cassi_resonant_field as field
import run_fractal_parent_summary_retention as runner


@pytest.fixture(scope="module")
def receipt() -> dict:
    built = runner.build_receipt()
    assert built["verdict"] == "PASS_FIELD_OWNED_PARENT_SUMMARY_RETENTION"
    assert runner.verify_receipt(built)["content_digest_matches"]
    return built


def test_schema_and_causal_schedule(receipt: dict) -> None:
    assert receipt["schema"] == runner.SCHEMA
    assert receipt["declared"]["semantic_memory_claim"] is False
    assert receipt["declared"]["path"] == "L"
    assert receipt["declared"]["fine_path"] == "LL"
    assert receipt["effects"]["second_LL_successor_changes_state"]
    assert receipt["effects"]["stored_summary_equal_after_change_vs_noop"]
    assert receipt["effects"]["live_L_recompute_drift_after_change"] > runner.MARGIN


def test_source_off_direct_read_checkpoint_and_bypass(receipt: dict) -> None:
    assert receipt["source_off_advance"]["source_enabled"] is False
    assert receipt["reads"]["post_write"]["stored"]["present"] is True
    assert receipt["reads"]["checkpoint"]["summary_sha256"] == receipt["reads"]["direct_without_live_recompute"]["summary_sha256"]
    assert receipt["effects"]["checkpoint_direct_read_equal"]
    assert receipt["effects"]["direct_read_called_analyzer"] is False
    control = receipt["controls"]["direct_read_analyzer_bypass"]
    assert control["attempted"] and control["can_fail"] and not control["analyzer_called"]


def test_firing_serialized_register_mutation(receipt: dict) -> None:
    control = receipt["controls"]["serialized_register_mutation"]
    assert control["attempted"]
    assert not control["accepted"]
    assert control["can_fail"]
    assert control["error_type"] == "ResonantNumericalError"
    assert "digest mismatch" in control["error"]


def test_absent_legacy_workspace_remains_compatible() -> None:
    workspace = field.initial_workspace()
    roundtrip = field.ResonantWorkspace.from_dict(workspace.as_dict())
    read = field.read_parent_summary(roundtrip)
    assert read["present"] is False
    assert read["values"] is None


def test_active_register_is_explicitly_rejected_by_other_layout_paths() -> None:
    first, _ = runner._impulse(field.initial_workspace(), runner.FIRST_SIGNAL, runner.FIRST_BUDGET)
    stored, _ = field.write_parent_summary(first)
    with pytest.raises(field.ResonantNumericalError, match="regional serialization rejects"):
        field.regional_state(stored)
    with pytest.raises(field.ResonantNumericalError, match="resolution change rejects"):
        field.expand_resolution(stored, factor=2)


def test_write_predecessor_is_immutable_and_bind_advance_impulse_preserve() -> None:
    origin = field.initial_workspace()
    first, _ = runner._impulse(origin, runner.FIRST_SIGNAL, runner.FIRST_BUDGET)
    before_state, before_page = first.state_sha256, first.page_bytes
    stored, receipt = field.write_parent_summary(first)
    assert first.state_sha256 == before_state
    assert first.page_bytes == before_page
    assert receipt["source_state_sha256"] == before_state
    advanced, _ = field.advance_workspace(stored, ticks=1, source_enabled=False)
    assert field.read_parent_summary(advanced)["summary_sha256"] == field.read_parent_summary(stored)["summary_sha256"]
    changed, _ = runner._impulse(advanced, runner.CHANGE_SIGNAL, runner.CHANGE_BUDGET)
    assert field.read_parent_summary(changed)["summary_sha256"] == field.read_parent_summary(stored)["summary_sha256"]
    bound = field.bind_workspace(
        stored,
        field.ResonantProblem(variable_ids=("x",), precision=[[1.0]]),
    )
    assert field.read_parent_summary(bound)["summary_sha256"] == field.read_parent_summary(stored)["summary_sha256"]


def test_generated_receipt_schema_is_persistable(tmp_path: Path) -> None:
    receipt = runner.build_receipt()
    path = tmp_path / "retention.json"
    path.write_text(json.dumps(receipt, sort_keys=True), encoding="utf-8")
    loaded = json.loads(path.read_text(encoding="utf-8"))
    assert runner.verify_receipt(loaded)["content_digest_matches"]
