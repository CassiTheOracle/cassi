"""Focused tests for the active arrangement comparison receipt."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np
import pytest

import run_fractal_arrangement_comparison as arrangement

RECEIPT = Path(__file__).parent / "_diag" / "fractal-arrangement-comparison" / "exploration.json"


def load_receipt() -> dict:
    assert RECEIPT.exists(), f"missing receipt: {RECEIPT}"
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_digest_clock_strip_and_mutation_control():
    receipt = load_receipt()
    assert arrangement.content_digest(receipt) == receipt["content_digest"]
    mutated = copy.deepcopy(receipt)
    mutated["arms"][0]["measurements"]["write"]["write_reach_l2"] += 0.25
    assert arrangement.content_digest(mutated) != receipt["content_digest"]


def test_three_named_arms_use_active_hooks_and_matched_budgets():
    receipt = load_receipt()
    assert [row["label"] for row in receipt["arms"]] == [
        "current-meaningful-helix", "core-shell-loops", "nested-paired-loops"
    ]
    for arm in receipt["arms"]:
        hooks = arm["operators"]
        assert all(hooks[name] for name in (
            "projected_transport",
            "projected_inv_mass",
            "projected_quartic_weights",
        ))
        assert arm["placement"]["public_BC_matrices"] is False
        assert arm["budgets"]["pools"] == 7.0
        assert arm["budgets"]["ports_per_pool"] == 4.0
    budgets = receipt["declared"]["budgets"]
    assert all(row["budgets"]["coupling"] == pytest.approx(budgets["coupling"]) for row in receipt["arms"])
    assert all(row["budgets"]["active_edge_l1"] == pytest.approx(budgets["active_edge_l1"]) for row in receipt["arms"])
    assert all(row["budgets"]["total_inverse_mass"] == pytest.approx(budgets["total_inverse_mass"]) for row in receipt["arms"])


def test_required_measurements_and_real_silenced_controls():
    receipt = load_receipt()
    for arm in receipt["arms"]:
        measures = arm["measurements"]
        assert measures["write"]["write_reach_l2"] > arrangement.WRITE_REACH_MARGIN
        assert measures["read_projection"]["sensitivity_l2"] > arrangement.READ_SENSITIVITY_MARGIN
        assert "observed_share_at_final_tick" in measures["cross_talk"]
        assert len(measures["observations"]) == len(arrangement.OBSERVATION_TICKS)
        assert "return_windows" in measures["persistence"]
        silence = arm["silenced_control"]
        assert silence["attempted"] is True
        assert silence["write_reach_l2"] == pytest.approx(0.0)
        assert silence["persistence_initial_alignment"] == pytest.approx(0.0)


def test_can_fail_predicates_are_firing_controls():
    receipt = load_receipt()
    probes = arrangement.can_fail_probes(receipt)
    assert probes["all_fire"] is True
    assert all(probes["silenced_arm_predicates_fire"].values())
    assert all(probes["mutated_comparison_predicates_fire"])


def test_continuity_reproduces_two_existing_geometry_values():
    receipt = load_receipt()
    checks = receipt["continuity_checks"]
    assert len(checks) >= 2
    assert all(row["within_tolerance"] for row in checks)
    assert {row["arrangement"] for row in checks} >= {"helix7", "recursive-paired-loops"}


def test_rebuild_is_content_deterministic():
    first = arrangement.build_receipt()
    second = arrangement.build_receipt()
    assert first["content_digest"] == second["content_digest"]
    assert first["content_digest"] == arrangement.content_digest(first)
    assert np.isfinite(first["arms"][0]["measurements"]["write"]["write_reach_l2"])
