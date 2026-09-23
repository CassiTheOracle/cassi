"""Focused tests for temporal localized-field survival."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

import run_fractal_temporal_survival_exploration as temporal

RECEIPT = Path(__file__).resolve().parent / "_diag" / "fractal-temporal-survival" / "exploration.json"


def receipt() -> dict:
    assert RECEIPT.exists(), (
        f"Missing receipt {RECEIPT}; run `python run_fractal_temporal_survival_exploration.py "
        "--output _diag/fractal-temporal-survival/exploration.json` from CassiFI."
    )
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_schema_digest_and_clock_strip_are_real() -> None:
    built = receipt()
    assert built["schema"] == temporal.SCHEMA
    assert temporal.verify_receipt(built)["content_digest_matches"]
    clocked = copy.deepcopy(built)
    clocked["runtime_seconds"] = 999.0
    clocked["elapsed_seconds"] = 1000.0
    assert temporal.content_digest(clocked) == built["content_digest"]
    mutated = copy.deepcopy(built)
    mutated["arms"]["fine-LL-source-off"]["samples"][1]["child_delta_norm"] = 0.0
    assert temporal.content_digest(mutated) != built["content_digest"]


def test_declared_arm_matrix_schedule_and_public_correction_api() -> None:
    built = receipt()
    assert set(built["arms"]) == {
        "no-write-source-off",
        "fine-LL-source-off",
        "fine-LR-source-off",
        "fine-LL-child-correction",
    }
    assert built["declared"]["packet_paths"] == {
        "parent": "L",
        "fine_child": "LL",
        "sibling_null": "LR",
    }
    assert built["declared"]["schedule"] == {
        "sample_ticks": [0, 1, 2, 4, 8, 16, 32, 64],
        "correction_tick": 8,
        "source_enabled": False,
        "demand": 0.0,
    }
    assert built["arms"]["no-write-source-off"]["write_impulse"] is None
    assert built["arms"]["fine-LL-source-off"]["write_impulse"]["path"] == "LL"
    assert built["arms"]["fine-LR-source-off"]["write_impulse"]["path"] == "LR"
    correction = built["arms"]["fine-LL-child-correction"]["correction_impulse"]
    assert correction["accepted"] is True
    assert correction["path"] == "LL"
    assert correction["flow_signal"] == [-1.0, 0.0]
    assert built["arms"]["fine-LL-child-correction"]["correction_pre"]["tick"] == temporal.CORRECTION_TICK
    assert built["arms"]["fine-LL-child-correction"]["correction_post"]["tick"] == temporal.CORRECTION_TICK


def test_source_off_telemetry_is_explicit_and_finite() -> None:
    built = receipt()
    for arm in built["arms"].values():
        for row in arm["samples"]:
            assert row["source_enabled"] is False
            assert row["positive_heartbeat_work"] == 0.0
            assert row["finite"] is True
            assert np.isfinite(row["child_norm"])
            assert np.isfinite(row["parent_summary_norm"])


def test_continuity_reproduces_two_localized_projection_figures() -> None:
    built = receipt()
    assert built["continuity_verdict"] == "PASS"
    assert len(built["continuity"]) == 2
    expected = {
        "comparisons[id=fine_child_reaches].quantity": 0.04711169913218956,
        "comparisons[id=coarse_projection_separates_LL_from_LR].quantity": 0.008279320196523436,
    }
    for row in built["continuity"]:
        assert row["expected"] == expected[row["selector"]]
        assert row["measured"] == row["expected"]
        assert row["within_tolerance"] is True
        assert abs(row["difference"]) <= temporal.CONTINUITY_TOLERANCE


def test_temporal_observables_include_threshold_crossings_occupancy_and_returns() -> None:
    built = receipt()
    for name in ("fine-LL-source-off", "fine-LL-child-correction"):
        trajectory = built["trajectories"][name]
        assert trajectory["alignment_threshold_fraction"] == temporal.ALIGNMENT_THRESHOLD_FRACTION
        assert [row["tick"] for row in trajectory["samples"]] == list(temporal.SAMPLE_TICKS)
        assert 0.0 <= trajectory["child_occupancy_fraction"] <= 1.0
        assert 0.0 <= trajectory["parent_occupancy_fraction"] <= 1.0
        assert trajectory["child_return_window_count"] >= 0
        assert trajectory["parent_return_window_count"] >= 0
        assert trajectory["initial_child_delta_norm"] > temporal.FINE_REACH_MARGIN
        assert trajectory["initial_parent_delta_norm"] > temporal.PROJECTION_SEPARATION_MARGIN


def test_comparisons_and_firing_controls_are_live() -> None:
    built = receipt()
    probes = temporal.can_fail_probes(built)
    assert probes == {
        "comparison_count": 7,
        "control_count": 7,
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


def test_expected_verdict_boundary_and_runtime() -> None:
    built = receipt()
    assert built["declared"]["semantic_recall_claim"] is False
    assert built["declared"]["field_persistence_claim"] is False
    assert "persistent parent/child" in built["boundary"]
    assert any("second" in item and "impulse" in item for item in built["limitations"])
    assert any("semantic memory" in item for item in built["limitations"])
    assert float(built["runtime_seconds"]) < 180.0
    assert built["verdict"] in {
        "MEASURED_FIELD_TEMPORAL_SURVIVAL_NO_PERSISTENT_PARENT_CHILD_MEMORY",
        "MEASURED_NO_FIELD_TEMPORAL_SURVIVAL_OR_PERSISTENT_PARENT_CHILD_MEMORY",
    }
