"""Focused checks for opaque candidate-set recovery."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_task_conditioned_memory_consumer as probe


@pytest.fixture(scope="module")
def receipt() -> dict:
    return probe.build_receipt()


def _by_name(receipt: dict) -> dict:
    return {row["name"]: row for row in receipt["episodes"]}


def test_public_probe_is_measured_and_independently_verifiable(receipt: dict) -> None:
    check = probe.verify_receipt(receipt)
    assert receipt["status"] == "MEASURED"
    assert check["content_digest_matches"] is True
    assert check["episode_count"] == 8
    assert receipt["numeric_policy"] == {"dtype": "float64", "device": "cpu", "numpy_seterr": "raise", "seed": probe.SEED}


def test_four_candidates_are_orthogonal_and_digest_tie_break_is_declared(receipt: dict) -> None:
    assert len(receipt["candidate_directions"]) == 4
    assert len({row["direction_sha256"] for row in receipt["candidate_directions"]}) == 4
    assert receipt["orthogonality"]["within_allowance"] is True
    selection = receipt["declared_task"]["selection"]
    assert "direction digest" in selection
    assert "presentation index" in selection


def test_train_and_heldout_set_recovery_are_exact(receipt: dict) -> None:
    evaluation = receipt["evaluation"]
    assert evaluation["train"] == {"total": 2, "exact_set_matches": 2}
    heldout = evaluation["held_out_permutation"]
    assert heldout["exact_set_match"] is True
    assert heldout["precision"] == pytest.approx(1.0)
    assert heldout["recall"] == pytest.approx(1.0)
    assert heldout["selection_margin"] > 0.0


def test_order_permutation_and_action_permutation_controls_fire(receipt: dict) -> None:
    rows = _by_name(receipt)
    heldout = rows["held-out:permutation"]
    order = rows["control:order-permutation"]
    assert heldout["presentation_order"] != order["presentation_order"]
    assert heldout["selected_set"] == order["selected_set"]
    assert heldout["action_order"] != order["action_order"]
    assert order["exact_set_match"] is True
    assert receipt["controls"]["cue_action_permutation"] is True


def test_blank_decoy_suppressed_and_unconditional_controls_are_observable(receipt: dict) -> None:
    rows = _by_name(receipt)
    blank = rows["control:blank-no-memory"]
    assert blank["writes"] == []
    assert blank["read_calls"] == 4
    assert blank["exact_set_match"] is False
    decoy = rows["control:decoy-only"]
    suppressed = rows["control:same-page-read-suppressed"]
    firing = rows["control:unconditional-policy-firing"]
    assert blank["writes"] == []
    assert blank["read_calls"] == 4
    assert decoy["exact_set_match"] is False
    assert suppressed["read_calls"] == 0
    assert suppressed["instrument_read"] is not None
    assert suppressed["exact_set_match"] is False
    assert len(firing["acts"]) == 2
    assert all(act["accepted"] for act in firing["acts"])
    assert firing["exact_set_match"] is False
    assert firing["selected_set"] != firing["hidden_set"]
    assert receipt["controls"]["blank_no_memory"] is True
    assert receipt["controls"]["decoy"] is True
    assert receipt["controls"]["same_page_read_suppressed"] is True
    assert receipt["controls"]["unconditional_policy_firing"] is True


def test_each_selected_direction_has_one_owner_act_and_margin(receipt: dict) -> None:
    for row in receipt["episodes"][:3]:
        assert len(row["selected_set"]) == 2
        assert len(row["acts"]) == 2
        assert {act["direction"] for act in row["acts"]} == set(row["selected_set"])
        assert all(act["accepted"] for act in row["acts"])
        assert row["selection_margin"] > 0.0


def test_continuity_values_are_reproduced(receipt: dict) -> None:
    continuity = receipt["continuity"]
    assert continuity["write_budget"]["within_tolerance"] is True
    assert continuity["greatest_off_diagonal_squared_cosine"]["within_tolerance"] is True


def test_content_digest_detects_measurement_mutation(receipt: dict) -> None:
    mutated = copy.deepcopy(receipt)
    mutated["episodes"][0]["selection_margin"] += 1e-6
    assert probe.verify_receipt(mutated)["content_digest_matches"] is False


def test_receipt_lands_at_declared_new_workstream_path(receipt: dict) -> None:
    path = Path("_diag/task-conditioned-memory-consumer/exploration.json")
    assert path.exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["content_digest"] == receipt["content_digest"]
