"""Fast contract checks for the field-coordinate cue/action probe."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_cue_conditioned_field_action as probe
import verify_cue_conditioned_field_action as independent


@pytest.fixture(scope="module")
def receipt() -> dict:
    return probe.build_receipt()


def _rows(receipt: dict) -> dict:
    return {row["name"]: row for row in receipt["episodes"]}


def test_observable_field_controller_contract(receipt: dict) -> None:
    assert receipt["status"] == "MEASURED"
    assert receipt["schema"] == probe.SCHEMA
    assert receipt["numeric_policy"] == {"dtype": "float64", "device": "cpu", "numpy_seterr": "raise", "seed": probe.SEED}
    assert receipt["protocol"]["adaptive_state"] == "the live resonant field only"
    assert receipt["protocol"]["semantic_claim"] is False
    assert len(receipt["cue_directions"]) == 4
    assert len({row["direction_sha256"] for row in receipt["cue_directions"]}) == 4
    assert receipt["orthogonality"]["within_allowance"] is True
    for row in receipt["episodes"][:3]:
        assert row["read_calls"] == 4
        assert row["selection_margin"] > row["selection_margin_floor"]
        assert len(row["acts"]) == 2
        assert all(act["accepted"] for act in row["acts"])
        assert all(act["owner_write_delta_energy"] > 0.0 for act in row["acts"])
        assert all(act["share_along_action_direction"] >= receipt["controls"]["action_share_floor"] for act in row["acts"])


def test_training_and_held_out_combination(receipt: dict) -> None:
    evaluation = receipt["evaluation"]
    assert evaluation["training"] == {"total": 2, "exact_cue_set_matches": 2, "action_sequence_matches": 2}
    heldout = evaluation["held_out_combination"]
    assert heldout["exact_cue_set_match"] is True
    assert heldout["action_sequence_match"] is True
    assert heldout["selection_margin"] > receipt["controls"]["selection_margin_floor"]
    row = _rows(receipt)["held-out:combination"]
    assert row["presentation_order"] != list(probe.HELD_OUT_CUES)
    assert {act["action_direction"] for act in row["acts"]} == set(row["selected_actions"])
    assert all(act["target_action"] == probe.CUE_TO_ACTION[act["cue"]] for act in row["acts"])


def test_all_controls_are_attempted_and_fire(receipt: dict) -> None:
    rows = _rows(receipt)
    assert set(receipt["controls"]["attempted"]) == {"blank_no_memory", "cue_read_suppressed", "wrong_cue_action_mapping", "unconditional_fixed_action", "action_order_permutation"}
    assert all(receipt["controls"][key] is True for key in receipt["controls"]["attempted"])
    assert rows["control:blank-no-memory"]["writes"] == []
    assert rows["control:cue-read-suppressed"]["read_calls"] == 0
    assert rows["control:cue-read-suppressed"]["suppressed_probe"] is not None
    assert rows["control:wrong-cue-action-mapping"]["exact_cue_set_match"] is True
    assert rows["control:wrong-cue-action-mapping"]["action_sequence_match"] is False
    assert all(act["action_direction"] != probe.CUE_TO_ACTION[act["cue"]] for act in rows["control:wrong-cue-action-mapping"]["acts"])
    assert rows["control:unconditional-fixed-action"]["mode"] == "unconditional"
    assert rows["control:unconditional-fixed-action"]["selected_cues"] == list(probe.CUE_NAMES[:2])
    digests = {row["name"]: row["direction_sha256"] for row in receipt["cue_directions"]}
    assert rows["control:unconditional-fixed-action"]["selected_cues"] != probe._select(rows["control:unconditional-fixed-action"]["scores"], digests)
    assert all(act["accepted"] for act in rows["control:unconditional-fixed-action"]["acts"])
    assert rows["control:action-order-permutation"]["selected_cues"] == rows["held-out:combination"]["selected_cues"]
    assert rows["control:action-order-permutation"]["action_order"] != rows["held-out:combination"]["action_order"]
    assert rows["control:action-order-permutation"]["action_sequence_match"] is False
    assert all(value is True for value in receipt["controls"]["firing"].values())


def test_continuity_and_independent_verifier_agree(receipt: dict) -> None:
    assert receipt["continuity"]["write_budget"]["within_tolerance"] is True
    assert receipt["continuity"]["greatest_off_diagonal_squared_cosine"]["within_tolerance"] is True
    result = independent.verify(receipt)
    assert result["status"] == "VERIFIED"
    assert result["content_digest"] == receipt["content_digest"]
    assert result["positive_anchor"] is True
    assert result["negative_anchor"] is True


def test_digest_mutation_is_rejected(receipt: dict) -> None:
    mutated = copy.deepcopy(receipt)
    mutated["episodes"][0]["selection_margin"] += 1e-6
    assert probe.verify_receipt(mutated)["content_digest_matches"] is False
    with pytest.raises(AssertionError):
        independent.verify(mutated)


def test_receipt_lands_at_declared_path(receipt: dict) -> None:
    path = Path("_diag/cue-conditioned-field-action/exploration.json")
    assert path.exists()
    on_disk = json.loads(path.read_text(encoding="utf-8"))
    assert on_disk["schema"] == probe.SCHEMA
    assert on_disk["content_digest"] == receipt["content_digest"]
