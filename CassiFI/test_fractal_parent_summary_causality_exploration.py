"""Focused tests for the LL intervention/coarse-summary capability probe."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

import run_fractal_parent_summary_causality_exploration as causal

RECEIPT = (
    Path(__file__).resolve().parent
    / "_diag"
    / "fractal-parent-summary-causality"
    / "exploration.json"
)


def receipt() -> dict:
    assert RECEIPT.exists(), (
        f"Missing receipt {RECEIPT}; run `python run_fractal_parent_summary_causality_exploration.py "
        "--output _diag/fractal-parent-summary-causality/exploration.json` from CassiFI."
    )
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_schema_digest_and_clock_strip_are_real() -> None:
    built = receipt()
    assert built["schema"] == causal.SCHEMA
    assert causal.verify_receipt(built)["content_digest_matches"]
    clocked = copy.deepcopy(built)
    clocked["runtime_seconds"] = 999.0
    clocked["elapsed_seconds"] = 1000.0
    assert causal.content_digest(clocked) == built["content_digest"]
    mutated = copy.deepcopy(built)
    mutated["observables"]["fine_intervention_effect_norm"] = 0.0
    assert causal.content_digest(mutated) != built["content_digest"]


def test_arm_matrix_uses_only_LL_and_shares_the_initial_branch() -> None:
    built = receipt()
    assert set(built["arms"]) == {
        "no-write-source-off",
        "LL-read-then-LL-change",
        "LL-read-then-LL-noop",
    }
    assert built["declared"]["arm_matrix"] == [
        "no-write-source-off",
        "LL-read-then-LL-change",
        "LL-read-then-LL-noop",
    ]
    changed = built["arms"]["LL-read-then-LL-change"]
    noop = built["arms"]["LL-read-then-LL-noop"]
    assert changed["write_path"] == "LL"
    assert changed["first_impulse"]["path"] == "LL"
    assert changed["second_impulse"]["path"] == "LL"
    assert changed["second_impulse"]["accepted"] is True
    assert changed["second_impulse"]["flow_signal"] == [0.0, 1.0]
    assert noop["first_impulse"]["path"] == "LL"
    assert noop["second_impulse"]["path"] == "LL"
    assert noop["second_impulse"]["accepted"] is False
    assert all(
        impulse["path"] == "LL"
        for arm in (changed, noop)
        for impulse in (arm["first_impulse"], arm["second_impulse"])
    )
    assert changed["initial_state_sha256"] == noop["initial_state_sha256"]
    assert changed["first_impulse"]["state_sha256"] == noop["first_impulse"]["state_sha256"]


def test_schedule_reads_parent_before_change_and_observes_source_off() -> None:
    built = receipt()
    for arm in built["arms"].values():
        reads = arm["reads"]
        assert [reads[name]["phase"] for name in ("post_first_write", "pre_second_action", "post_second_action")] == [
            "post-first-write",
            "pre-second-action",
            "post-second-action",
        ]
        assert reads["post_first_write"]["parent_path"] == "L"
        assert reads["post_first_write"]["fine_path"] == "LL"
        if arm["first_impulse"] is None:
            assert (
                reads["post_first_write"]["parent_source_state_sha256"]
                == reads["post_first_write"]["state_sha256"]
            )
        else:
            assert (
                reads["post_first_write"]["parent_source_state_sha256"]
                == arm["first_impulse"]["state_sha256"]
            )
        for row in reads.values():
            assert row["finite"] is True
            assert np.isfinite(row["parent_level_zero_projection"]).all()
            assert np.isfinite(row["fine_coefficients"]).all()
        advance = arm["source_off_advance"]
        assert advance["source_enabled"] is False
        assert advance["positive_heartbeat_work"] == 0.0
        assert advance["ticks"] == causal.SOURCE_OFF_TICKS


def test_second_LL_intervention_changes_fine_detail_and_noop_is_identity() -> None:
    built = receipt()
    rows = {row["id"]: row for row in built["comparisons"]}
    assert rows["fine_LL_intervention_changes_live_child"]["holds"] is True
    assert built["observables"]["fine_intervention_effect_norm"] > causal.FINE_CHANGE_MARGIN
    assert rows["LL_noop_preserves_read_at_fixed_state"]["holds"] is True
    assert built["observables"]["fine_live_change_norm"] > causal.FINE_CHANGE_MARGIN
    assert built["observables"]["parent_intervention_effect_norm"] >= 0.0
    assert built["observables"]["live_parent_recompute_drift_norm"] >= 0.0


def test_real_mixed_source_parent_reuse_refuses() -> None:
    built = receipt()
    reuse = built["mixed_source_parent_reuse"]
    assert reuse["attempted"] is True
    assert reuse["accepted"] is False
    assert reuse["error_type"] == "ResonantNumericalError"
    assert "source state" in reuse["error"]
    assert reuse["same_source_state"] is False
    assert reuse["old_right_source_state_sha256"] != reuse["new_fine_source_state_sha256"]


def test_frozen_parent_capability_is_explicitly_out_of_scope() -> None:
    built = receipt()
    probe = built["api_probe"]
    assert probe["live_path_available"] is True
    assert all(value is False for value in probe["frozen_parent_api_symbols"].values())
    unsupported = probe["coarse_only_frozen_parent"]
    assert unsupported["available"] is False
    assert unsupported["attempted"] is False
    assert unsupported["verdict"] == "OUT_OF_SCOPE"
    summary = built["summary_persistence"]
    assert summary["attempted"] is False
    assert summary["verdict"] == "NOT_APPLICABLE"
    assert built["declared"]["semantic_recall_claim"] is False
    assert built["declared"]["field_persistence_claim"] is False
    assert built["declared"]["persistent_parent_claim"] is False


def test_comparison_controls_are_attempted_can_fail_and_flip() -> None:
    built = receipt()
    probes = causal.can_fail_probes(built)
    assert probes == {
        "comparison_count": 4,
        "control_count": 4,
        "all_attempted": True,
        "all_can_fail": True,
        "all_flip": True,
    }
    assert built["controls"]["all_attempted"] is True
    assert built["controls"]["all_can_fail"] is True
    assert built["controls"]["all_flip"] is True
    for row in built["comparisons"]:
        assert row["firing_control"]["attempted"] is True
        assert row["firing_control"]["can_fail"] is True
        assert row["firing_control"]["holds_after"] is False


def test_continuity_verifies_two_prior_localized_figures() -> None:
    built = receipt()
    assert built["continuity_verdict"] == "PASS"
    expected = {
        "comparisons[id=fine_child_reaches].quantity": 0.04711169913218956,
        "comparisons[id=coarse_projection_separates_LL_from_LR].quantity": 0.008279320196523436,
    }
    assert len(built["continuity"]) == 2
    for row in built["continuity"]:
        assert row["expected"] == expected[row["selector"]]
        assert row["measured"] == row["expected"]
        assert row["within_tolerance"] is True
        assert abs(row["difference"]) <= causal.CONTINUITY_TOLERANCE


def test_verdict_boundary_and_runtime_are_explicit() -> None:
    built = receipt()
    assert built["verdict"] == "OUT_OF_SCOPE_FROZEN_PARENT_RECOVERY_NO_API"
    assert "not retained parent state" in built["boundary"]
    assert any("persistent" in item for item in built["limitations"])
    assert any("semantic memory" in item for item in built["limitations"])
    assert float(built["runtime_seconds"]) < 180.0
