"""Focused integrity and behavior checks for the matched geometry-pair runner."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_geometry_pair_exploration as pair


@pytest.fixture(scope="module")
def receipt(tmp_path_factory: pytest.TempPathFactory) -> dict:
    output = tmp_path_factory.mktemp("geometry-pair") / "exploration.json"
    assert pair.main(["--output", str(output)]) == 0
    return json.loads(output.read_text(encoding="utf-8"))


def test_receipt_freezes_declared_pairs_grid_and_complete_cells(receipt: dict):
    assert receipt["schema"] == pair.SCHEMA
    assert [(row["left"], row["right"]) for row in receipt["declared"]["pairs"]] == [
        ("flat-ladder", "random-rewire-matched"),
        ("flat-ladder", "quasiperiodic-chain"),
    ]
    grid = receipt["declared"]["factor_grid"]
    assert grid["metric"] == list(pair.METRICS)
    assert grid["wiring"] == list(pair.WIRINGS)
    assert grid["capacity"] == list(pair.CAPACITY_COUNTS)
    assert grid["placement"] == list(pair.PLACEMENTS)
    assert len(receipt["comparisons"]) == len(pair.PAIRS) * len(pair.METRICS) * len(pair.WIRINGS) * len(pair.CAPACITY_COUNTS)
    assert receipt["declared"]["headline"] == {
        "metric": "canonical",
        "wiring": "native",
        "placement": "canonical-port-0",
        "capacities": list(pair.CAPACITY_COUNTS),
        "recovery_margin": pair.RECOVERY_MARGIN,
    }


def test_edge_matching_is_measured_and_can_fail_on_a_real_leaf_mutation(receipt: dict):
    checks = receipt["edge_match_checks"]
    assert len(checks) == len(pair.PAIRS) * len(pair.METRICS) * len(pair.WIRINGS)
    assert all(row["link_count_equal"] for row in checks)
    assert all(row["cross_pool_l1_equal_within_tolerance"] for row in checks)
    assert all(row["matched"] for row in checks)

    mutated = copy.deepcopy(receipt)
    mutated["profiles"]["random-rewire-matched|canonical|native"]["edge"]["effective_link_count"] += 1
    left = mutated["profiles"]["flat-ladder|canonical|native"]["edge"]
    right = mutated["profiles"]["random-rewire-matched|canonical|native"]["edge"]
    assert pair.edge_match(left, right)["matched"] is False


def test_comparisons_have_can_fail_margins_and_secondary_controls(receipt: dict):
    assert receipt["controls"]["silenced_cross_scale"]["attempted"] is True
    assert receipt["controls"]["shell_metric"]["attempted"] is True
    assert receipt["controls"]["seeded_shuffle_placement"]["attempted"] is True
    assert all(row["placement"] == "canonical-port-0" for row in receipt["comparisons"])
    assert all(row["margin"] == pair.RECOVERY_MARGIN and row["margin"] > 0 for row in receipt["comparisons"])
    assert all(row["firing_control"]["attempted"] and row["firing_control"]["can_fail"] for row in receipt["comparisons"])
    assert all(row["firing_control"]["can_fail"] for row in receipt["placement_checks"])
    assert all(row["mode_margin"] == pair.PLACEMENT_MODE_MARGIN for row in receipt["placement_checks"])


def test_continuity_digest_and_explicit_scope(receipt: dict):
    assert len(receipt["continuity_checks"]) >= 2
    assert all(row["within_tolerance"] for row in receipt["continuity_checks"])
    assert receipt["verdicts"]["continuity"] == "PASS"
    assert receipt["limitations"]
    assert any("delayed-binding API" in item for item in receipt["limitations"])
    assert any("compositional semantic recall" in item for item in receipt["limitations"])

    mutated = copy.deepcopy(receipt)
    mutated["comparisons"][0]["difference_right_minus_left"] += 0.125
    assert pair.content_digest(mutated) != receipt["content_digest"]
    clocked = copy.deepcopy(receipt)
    clocked["elapsed_seconds"] = 999.0
    clocked["runtime_seconds"] = 1000.0
    assert pair.content_digest(clocked) == receipt["content_digest"]
