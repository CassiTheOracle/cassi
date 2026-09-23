"""Focused contract tests for the fixed-graph causal arrangement receipt."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_causal_arrangement_exploration as causal

RECEIPT = Path(__file__).parent / "_diag" / "fractal-causal-arrangement" / "exploration.json"


def load_receipt() -> dict:
    assert RECEIPT.exists(), (
        f"Missing receipt {RECEIPT}; run "
        "`python run_fractal_causal_arrangement_exploration.py "
        "--output _diag/fractal-causal-arrangement/exploration.json` "
        "from CassiFI."
    )
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_digest_and_clock_strip_are_real():
    receipt = load_receipt()
    checked = causal.verify_receipt(receipt)
    assert checked["content_digest_matches"]
    timed = copy.deepcopy(receipt)
    timed["runtime_seconds"] = float(timed.get("runtime_seconds", 0.0)) + 1000.0
    timed["leg_a"]["arms"][0]["condensation"]["elapsed_seconds"] = 99.0
    assert causal.content_digest(timed) == receipt["content_digest"]
    mutated = copy.deepcopy(receipt)
    mutated["leg_a"]["arms"][1]["trajectory"][0]["output"] += 1.0
    assert causal.content_digest(mutated) != receipt["content_digest"]


def test_real_receipt_leaf_mutations_fire_can_fail_predicates():
    receipt = load_receipt()
    probes = causal.can_fail_probes(receipt)
    assert probes["placement_control_fires"]
    assert probes["metric_control_fires"]
    assert probes["placement_margin"] > 0.0


def test_fixed_graph_and_cross_scale_contract():
    receipt = load_receipt()
    for leg in (receipt["leg_a"], receipt["leg_b"]):
        assert leg["fixed_graph"]["arrangement"] == "helix7"
        assert leg["fixed_graph"]["topology"] == "meaningful-helix"
        assert leg["fixed_graph"]["port_count"] == 28
        assert leg["fixed_graph"]["projected_transport"] is None
        assert leg["fixed_graph"]["topology_sweep"] is False
    cross = receipt["declared"]["active_cross_scale"]
    assert cross["attempted"] is False
    assert cross["verdict"] == "OUT_OF_SCOPE"


def test_leg_a_uses_all_named_arms_and_records_actual_path():
    receipt = load_receipt()
    assert receipt["declared"]["leg_a"]["actual_path"] == "cassi_field_transceiver.condense_input -> advance_transceiver"
    assert receipt["declared"]["leg_a"]["not_modal_proxy"] is True
    names = [row["name"] for row in receipt["leg_a"]["arms"]]
    assert names == [
        "T0-canonical-inert",
        "T1-canonical-active",
        "T2-controllability-candidate",
        "T3-observability-candidate",
        "T4-joint-candidate",
        "T5-seeded-shuffle-active",
    ]
    for row in receipt["leg_a"]["arms"]:
        assert row["collision"]["collision_checked"]
        assert row["collision"]["valid"]
        assert row["binding_map_sha256"]
        assert row["input_lift_sha256"]
        assert row["output_rows_sha256"]
        assert row["reset_replay_identity"]["identical"]
        assert len(row["trajectory"]) == 64
        assert row["rank"] == 16
        assert row["horizon_ticks"] == 64
        assert row["envelope"] == pytest.approx(4.0)


def test_authority_control_and_comparison_margin_are_explicit():
    receipt = load_receipt()
    control = receipt["leg_a"]["authority_control"]
    assert control["margin"] == pytest.approx(1e-12)
    t0, t1 = receipt["leg_a"]["arms"][:2]
    assert t0["authority"]["spread"] <= 1e-12
    assert t1["authority"]["spread"] > 1e-12
    assert control["fires"]
    comparison = receipt["leg_a"]["comparison"]
    assert comparison["margin"] > 0.0
    assert comparison["interaction_tolerance"] == pytest.approx(0.01)


def test_leg_b_is_matched_two_by_three_and_reports_controls():
    receipt = load_receipt()
    arms = receipt["leg_b"]["arms"]
    assert len(arms) == 6
    assert {(row["metric"], row["damping"]) for row in arms} == {
        ("canonical", 0.006), ("canonical", 0.012), ("canonical", 0.024),
        ("mass-only", 0.006), ("mass-only", 0.012), ("mass-only", 0.024),
    }
    for row in arms:
        assert row["write_budget"] == pytest.approx(0.001)
        assert row["activity_ticks"] == 64
        assert row["activity_samples"] == [8, 16, 32, 64]
        assert row["source_off_ladder"]["horizon_ticks"] == 256
        assert row["source_off_ladder"]["sample_every"] == 16
        assert row["source_off_ladder"]["threshold_fraction"] == pytest.approx(0.05)
        assert row["restart_replay"]["state_digest_identical"]
        assert row["restart_replay"]["page_digest_identical"]
        assert "control_share" in row and "max_off_diagonal_confusion" in row
        assert "frame_energy_ratio" in row and "dissipated_work" in row
    comparisons = receipt["leg_b"]["comparisons"]
    assert comparisons["metric_margin"] == pytest.approx(0.02)
    assert comparisons["damping_recovery_margin"] == pytest.approx(0.02)
    assert comparisons["damping_lifetime_margin"] == 16
    assert comparisons["interaction_tolerance"] == pytest.approx(0.01)


def test_two_continuity_checks_are_present_and_finite():
    receipt = load_receipt()
    checks = receipt["continuity"]["checks"]
    assert len(checks) == 2
    assert receipt["continuity"]["all_within_tolerance"]
    assert all(row["expected"] is not None for row in checks)
    assert all(row["measured"] is not None for row in checks)
    assert all(row["within_tolerance"] for row in checks)
