"""Placement plumbing for the native latent-reasoning arms.

The model-side behaviour lives in `probe_cassi_coupling_placement.py`, which
needs the harness binary and a GGUF. These tests cover the parts that decide
what the harness is asked to run, because a wrong position convention or a
mismatched budget silently turns a placement comparison into a confounded one.
"""

from __future__ import annotations

import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

import run_cassi_latent_reasoning as latent  # noqa: E402


def schedule(**overrides):
    spec = {
        "coupled_steps": 16,
        "coupled_alpha": 0.01,
        "hold_steps": 4,
        "positions": [0, 1, 4],
    }
    spec.update(overrides)
    return spec


def test_schedule_lines_couple_named_positions_and_hold_the_rest() -> None:
    lines = latent.schedule_lines(schedule(), 6)
    assert lines == [
        "16 0.01",
        "16 0.01",
        "4 0.0",
        "4 0.0",
        "16 0.01",
        "4 0.0",
    ]


def test_schedule_lines_refuse_positions_outside_the_window() -> None:
    with pytest.raises(RuntimeError, match="outside the generation window"):
        latent.schedule_lines(schedule(positions=[0, 5]), 5)


def test_schedule_lines_refuse_a_zero_step_hold() -> None:
    with pytest.raises(RuntimeError, match="hold_steps must be at least 1"):
        latent.schedule_lines(schedule(hold_steps=0), 6)


def test_schedule_lines_accept_an_empty_schedule() -> None:
    assert latent.schedule_lines(schedule(positions=[]), 2) == ["4 0.0", "4 0.0"]


def comparison_row(budget: float, applied: int) -> dict[str, object]:
    return {
        "alpha": 0.01,
        "coupling_budget": budget,
        "field_steps": 4,
        "schedule_applied_entries": applied,
    }


def test_budget_check_matches_a_scheduled_arm_to_the_constant_reference() -> None:
    comparisons = {
        "k4_a01": comparison_row(1.28, 0),
        "place_front16": comparison_row(1.28, 32),
    }
    assert latent.check_coupling_budgets(comparisons) == {
        "reference_arm": "k4_a01",
        "reference_budget": 1.28,
        "reference_steps": 4,
        "reference_alpha": 0.01,
        "matched_arms": ["place_front16"],
    }


def test_budget_check_refuses_a_mismatched_scheduled_arm() -> None:
    comparisons = {
        "k4_a01": comparison_row(1.28, 0),
        "place_front16": comparison_row(12.8, 32),
    }
    with pytest.raises(RuntimeError, match="do not match the constant reference budget"):
        latent.check_coupling_budgets(comparisons)


def test_budget_check_refuses_a_missing_constant_reference() -> None:
    with pytest.raises(RuntimeError, match="need the constant k4_a01 arm"):
        latent.check_coupling_budgets({"place_front16": comparison_row(1.28, 32)})


def test_budget_check_is_silent_without_scheduled_arms() -> None:
    assert latent.check_coupling_budgets({"k4_a01": comparison_row(1.28, 0)}) is None
