"""Focused tests for the localized fine-write/coarse-view probe."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import numpy as np

import run_fractal_localized_projection_exploration as localized

RECEIPT = Path(__file__).resolve().parent / "_diag" / "fractal-localized-projection" / "exploration.json"


def receipt() -> dict:
    assert RECEIPT.exists(), (
        f"Missing receipt {RECEIPT}; run `python run_fractal_localized_projection_exploration.py "
        "--output _diag/fractal-localized-projection/exploration.json` from CassiFI."
    )
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_schema_digest_and_clock_strip_are_real() -> None:
    built = receipt()
    assert built["schema"] == localized.SCHEMA
    checked = localized.verify_receipt(built)
    assert checked["content_digest_matches"]

    clocked = copy.deepcopy(built)
    clocked["runtime_seconds"] = 999.0
    clocked["elapsed_seconds"] = 1000.0
    assert localized.content_digest(clocked) == built["content_digest"]

    mutated = copy.deepcopy(built)
    mutated["arms"]["fine-LL"]["page_sha256"] = "0" * 64
    assert localized.content_digest(mutated) != built["content_digest"]


def test_arm_matrix_is_exact_and_uses_declared_packet_supports() -> None:
    built = receipt()
    assert set(built["arms"]) == {"no-write", "fine-LL", "fine-LR", "coarse-L"}
    assert built["declared"]["packet_paths"] == {
        "parent": "L",
        "fine_child": "LL",
        "sibling_null": "LR",
    }
    assert built["declared"]["profile"]["ports_per_pool"] == 4
    assert built["arms"]["no-write"]["impulse"] is None
    assert built["arms"]["fine-LL"]["impulse"]["path"] == "LL"
    assert built["arms"]["fine-LR"]["impulse"]["path"] == "LR"
    assert built["arms"]["coarse-L"]["impulse"]["path"] == "L"
    for arm in built["arms"].values():
        views = arm["views"]
        assert views["parent"]["path"] == "L"
        assert views["fine_child"]["path"] == "LL"
        assert views["sibling_child"]["path"] == "LR"
        assert views["parent"]["source_state_sha256"] == arm["state_sha256"]


def test_write_receipts_are_bounded_and_controls_are_live() -> None:
    built = receipt()
    for name in ("fine-LL", "fine-LR", "coarse-L"):
        impulse = built["arms"][name]["impulse"]
        assert impulse["accepted"] is True
        assert impulse["requested_work"] == localized.DRIVE_BUDGET
        np.testing.assert_allclose(
            impulse["applied_work"],
            localized.DRIVE_BUDGET,
            rtol=0.0,
            atol=impulse["energy_roundoff_allowance"],
        )
        assert abs(impulse["balance_defect"]) <= impulse["energy_roundoff_allowance"]

    probes = localized.can_fail_probes(built)
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


def test_public_parent_split_compose_and_direct_child_comparisons_hold() -> None:
    built = receipt()
    rows = {row["id"]: row for row in built["comparisons"]}
    assert rows["parent_split_compose_reconstructs"]["holds"] is True
    assert rows["split_child_matches_direct_fine_view"]["holds"] is True
    assert rows["parent_split_compose_reconstructs"]["quantity"] <= localized.RECONSTRUCTION_MARGIN
    assert rows["split_child_matches_direct_fine_view"]["quantity"] <= localized.RECONSTRUCTION_MARGIN
    for name in ("fine-LL", "fine-LR", "coarse-L"):
        views = built["arms"][name]["views"]
        assert views["split_left"]["path"] == "LL"
        assert views["split_right"]["path"] == "LR"
        assert views["reconstructed_parent"]["path"] == "L"


def test_fine_child_reach_is_measured_against_silenced_control() -> None:
    built = receipt()
    row = next(row for row in built["comparisons"] if row["id"] == "fine_child_reaches")
    assert row["margin"] == localized.FINE_REACH_MARGIN
    assert row["quantity"] > row["margin"]
    assert row["firing_control"]["attempted"] is True
    assert row["firing_control"]["can_fail"] is True
    assert row["firing_control"]["holds_after"] is False


def test_coarse_projection_comparison_is_can_fail_and_negative_result_is_explicit() -> None:
    built = receipt()
    row = next(row for row in built["comparisons"] if row["id"] == "coarse_projection_separates_LL_from_LR")
    assert row["margin"] == localized.PROJECTION_SEPARATION_MARGIN
    assert row["firing_control"]["attempted"] is True
    assert row["firing_control"]["can_fail"] is True
    assert row["firing_control"]["holds_after"] is False
    if row["holds"]:
        assert built["verdict"] == "MEASURED_NO_VERDICT"
    else:
        assert built["verdict"] == "MEASURED_NO_PARENT_CHILD_MEMORY"


def test_continuity_runtime_and_boundary_are_explicit() -> None:
    built = receipt()
    assert len(built["continuity"]) >= 2
    assert built["continuity_verdict"] == "PASS"
    assert all(row["within_tolerance"] for row in built["continuity"])
    assert any("fractal-geometry" in row["source"] for row in built["continuity"])
    assert any("fractal-memory" in row["source"] for row in built["continuity"])
    assert float(built["runtime_seconds"]) < 180.0
    assert built["declared"]["semantic_recall_claim"] is False
    assert any("disposable" in item for item in built["limitations"])
    assert any("whole-page" in item for item in built["limitations"])
    assert any("persistent" in item for item in built["limitations"])
