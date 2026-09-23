"""Focused behavior and integrity checks for the factorial exploration."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import run_fractal_factorial_exploration as factorial


def run_to(path: Path) -> dict:
    assert factorial.main(["--output", str(path)]) == 0
    return json.loads(path.read_text(encoding="utf-8"))


def test_runner_freezes_complete_grid_factors_and_controls(tmp_path: Path):
    receipt = run_to(tmp_path / "one" / "exploration.json")
    assert receipt["schema"] == factorial.SCHEMA
    grid = receipt["declarations"]["grid"]
    assert grid["cells"] == 40
    assert grid["geometry"] == [name for name, _ in factorial.GEOMETRY_LEVELS]
    assert grid["metric"] == list(factorial.METRIC_LEVELS)
    assert grid["cross_scale_wiring"] == list(factorial.WIRING_LEVELS)
    assert grid["transceiver_placement"] == list(factorial.PLACEMENT_LEVELS)
    assert len(receipt["arms"]) == grid["cells"]
    assert {row["geometry"] for row in receipt["arms"]} == set(grid["geometry"])
    assert {row["metric"] for row in receipt["arms"]} == set(grid["metric"])
    assert {row["cross_scale_wiring"] for row in receipt["arms"]} == set(grid["cross_scale_wiring"])
    assert {row["placement"] for row in receipt["arms"]} == set(grid["transceiver_placement"])
    assert {"silenced_no_authority", "shuffled_placement", "receipt_mutation"} <= set(receipt["controls"])
    assert receipt["limitations"]
    assert len(receipt["continuity_checks"]) >= 2
    assert all(row["within_tolerance"] for row in receipt["continuity_checks"])


def test_digest_is_deterministic_and_clocks_are_excluded(tmp_path: Path):
    first = run_to(tmp_path / "first.json")
    second = run_to(tmp_path / "second.json")
    assert first["content_digest"] == second["content_digest"]
    assert first["receipt_sha256"] == first["content_digest"]
    clocked = copy.deepcopy(first)
    clocked["elapsed_seconds"] = 999.0
    clocked["runtime_seconds"] = 1000.0
    clocked["started_at"] = "later"
    clocked["finished_at"] = "later"
    assert factorial.content_digest(clocked) == first["content_digest"]


def test_digest_fires_on_real_measurement_mutation(tmp_path: Path):
    receipt = run_to(tmp_path / "exploration.json")
    mutated = copy.deepcopy(receipt)
    mutated["arms"][0]["alignment"][1] += 0.125
    assert factorial.content_digest(mutated) != receipt["content_digest"]
    # A declared clock mutation remains excluded, while the measured mutation fires.
    mutated["elapsed_seconds"] = 1.0
    assert factorial.content_digest(mutated) != receipt["content_digest"]


def test_lifetime_statistics_and_can_fail_controls_are_observed(tmp_path: Path):
    receipt = run_to(tmp_path / "exploration.json")
    for row in receipt["arms"]:
        assert row["samples"] == list(factorial.SAMPLES)
        assert len(row["alignment"]) == len(factorial.SAMPLES)
        assert row["first_crossing_tick"] in factorial.SAMPLES or row["first_crossing_tick"] is None
        assert 0.0 <= row["occupancy_fraction"] <= 1.0
        assert row["return_window_count"] >= 0
        assert row["exact_bilinear_prediction"]["used"] is True
    assert receipt["controls"]["silenced_no_authority"]["attempted"] is True
    assert receipt["controls"]["shuffled_placement"]["attempted"] is True
    comparisons = receipt["comparisons"]
    assert comparisons
    assert {item["comparison"] for item in comparisons} >= {
        "canonical-port-vs-shuffled-placement",
        "task-selected-vs-shuffled-placement",
        "native-vs-silenced-cross-scale",
        "canonical-vs-shell-metric",
    }
    for item in comparisons:
        assert item["margin"] > 0.0
        assert item["firing_control"]["attempted"] is True
        assert item["firing_control"]["can_fail"] is True
