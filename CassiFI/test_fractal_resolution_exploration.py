"""Focused integrity tests for the production coarse/fine resolution probe."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_resolution_exploration as resolution

RECEIPT = Path(__file__).resolve().parent / "_diag" / "fractal-resolution" / "exploration.json"


@pytest.fixture(scope="module")
def receipt() -> dict:
    assert RECEIPT.exists(), (
        f"Missing receipt {RECEIPT}; run `python run_fractal_resolution_exploration.py "
        "--output _diag/fractal-resolution/exploration.json` from CassiFI."
    )
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_schema_digest_and_clock_strip_are_real(receipt: dict) -> None:
    assert receipt["schema"] == resolution.SCHEMA
    checked = resolution.verify_receipt(receipt)
    assert checked["content_digest_matches"]

    clocked = copy.deepcopy(receipt)
    clocked["runtime_seconds"] = 999.0
    clocked["elapsed_seconds"] = 1000.0
    assert resolution.content_digest(clocked) == receipt["content_digest"]

    mutated = copy.deepcopy(receipt)
    mutated["source"]["state_sha256"] = "0" * 64
    assert resolution.content_digest(mutated) != receipt["content_digest"]


def test_scale_api_is_live_and_resolution_arms_are_not_fabricated(receipt: dict) -> None:
    probe = receipt["declared"]["api_probe"]
    assert probe["available"] is True
    assert all(probe["symbols"].values())
    assert probe["unsupported_arm"]["attempted"] is False
    assert probe["unsupported_arm"]["verdict"] == "NOT_APPLICABLE"

    expansion = receipt["arms"]["expansion"]
    reduction = receipt["arms"]["reduction"]
    assert expansion["from_ports_per_pool"] == 4
    assert expansion["to_ports_per_pool"] == 8
    assert expansion["transition"]["kind"] == "zero-mode-expansion"
    assert reduction["from_ports_per_pool"] == 8
    assert reduction["to_ports_per_pool"] == 4
    assert reduction["transition"]["kind"] == "orthonormal-passive-reduction"


def test_expansion_reduction_and_binding_comparisons_hold(receipt: dict) -> None:
    rows = {row["id"]: row for row in receipt["comparisons"]}
    assert set(rows) == {
        "expansion_zero_mode_embedding",
        "reduction_certificate_slack",
        "binding_survives_coarse_fine_transition",
    }
    for row in rows.values():
        assert row["margin"] > 0.0
        assert row["holds"] is True
        assert row["firing_control"]["attempted"] is True
        assert row["firing_control"]["can_fail"] is True
        assert row["firing_control"]["holds_after"] is False

    expansion = receipt["arms"]["expansion"]
    reduction = receipt["arms"]["reduction"]
    assert expansion["new_coordinates_zero"] is True
    assert expansion["transition"]["state_error_norm"] <= resolution.EXPANSION_MARGIN
    assert reduction["occupied_bindings_preserved"] is True
    assert reduction["slack"] >= resolution.REDUCTION_SLACK_MARGIN
    assert reduction["binding"]["port"] == receipt["source"]["binding"]["port"]
    assert receipt["verdict"] == "PASS"


def test_real_receipt_controls_can_fail(receipt: dict) -> None:
    probes = resolution.can_fail_probes(receipt)
    assert probes == {
        "comparison_count": 3,
        "control_count": 3,
        "all_attempted": True,
        "all_can_fail": True,
        "all_flip": True,
    }


def test_two_live_continuity_checks_reproduce_existing_figures(receipt: dict) -> None:
    checks = receipt["continuity"]
    assert len(checks) >= 2
    assert receipt["continuity_verdict"] == "PASS"
    assert all(row["within_tolerance"] for row in checks)
    assert all(row["expected"] is not None and row["measured"] is not None for row in checks)
    assert any("fractal-geometry" in row["source"] for row in checks)
    assert any("fractal-memory" in row["source"] for row in checks)


def test_runtime_and_boundary_are_explicit(receipt: dict) -> None:
    assert 0.0 <= float(receipt["runtime_seconds"]) < 180.0
    assert receipt["declared"]["semantic_recall_claim"] is False
    assert receipt["declared"]["probe_kind"] == "field-level boundary/surrogate probe"
    assert receipt["limitations"]
    assert any("semantic" in item for item in receipt["limitations"])
    assert any("packet" in item for item in receipt["limitations"])
