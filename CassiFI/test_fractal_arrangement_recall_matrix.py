"""Focused receipt-contract checks for the three-arm arrangement matrix."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_arrangement_recall_matrix as runner

RECEIPT = Path(__file__).parent / "_diag" / "fractal-arrangement-recall-matrix" / "exploration.json"
EXPECTED_LABELS = [
    "current-meaningful-helix",
    "nested-core-shell-loops",
    "nested-paired-loops",
]
EXPECTED_BUILDERS = ["helix7", "nested-core-shell", "recursive-paired-loops"]
EXPECTED_CONTINUITY = {
    "arrangements[construction.name=helix7].spectrum.ipr_median",
    "arrangements[construction.name=nested-core-shell].spectrum.ipr_median",
    "arrangements[construction.name=recursive-paired-loops].spectrum.ipr_median",
}
EXPECTED_CONTROLS = {"silenced", "no_memory", "mismatch", "policy_mutated"}
EXPECTED_CONSUMER_ARMS = {
    "A-memory-used",
    "B-identity-control-read-suppressed",
    "C-no-memory",
    "D-mismatch-control",
    "C-firing-control-policy-mutated",
}


def load_receipt() -> dict:
    assert RECEIPT.exists(), f"missing receipt: {RECEIPT}"
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_three_arm_order_and_shared_declared_contract() -> None:
    receipt = load_receipt()
    assert [arm["label"] for arm in receipt["arms"]] == EXPECTED_LABELS
    assert [arm["arrangement_name"] for arm in receipt["arms"]] == EXPECTED_BUILDERS
    declared = receipt["declared"]
    assert declared["task"] == "carry the remembered target direction forward"
    assert declared["candidate_directions"] == ["root-scale", "root-detail", "left-detail"]
    assert declared["write_budget"] == pytest.approx(1e-3)
    assert declared["act_budget"] == pytest.approx(1e-3)
    assert declared["hold_horizon_ticks"] == 16
    assert declared["controls"] == sorted(EXPECTED_CONTROLS, key=("silenced", "no_memory", "mismatch", "policy_mutated").index)
    assert set(declared["consumer_arms"]) == EXPECTED_CONSUMER_ARMS
    assert all(arm["declared_consumer"] == receipt["arms"][0]["declared_consumer"] for arm in receipt["arms"])


def test_every_arm_preserves_controls_and_status_classification() -> None:
    receipt = load_receipt()
    assert set(receipt["control_statuses"]) == set(EXPECTED_LABELS)
    for arm in receipt["arms"]:
        assert arm["status"] in {"MEASURED", "BLOCKED"}
        assert set(arm["consumer_arms"]) == EXPECTED_CONSUMER_ARMS
        assert set(arm["controls"]) == EXPECTED_CONTROLS
        assert set(receipt["control_statuses"][arm["label"]]) == EXPECTED_CONTROLS
        for name in EXPECTED_CONTROLS:
            control = arm["controls"][name]
            assert control["attempted"] is True
            assert control["status"] in {"MEASURED", "BLOCKED"}
            assert receipt["control_statuses"][arm["label"]][name]["status"] == control["status"]
        assert arm["owner_inspection"]["status"] == "MEASURED"
        assert arm["owner_inspection"]["canonical_json"] is True
        if arm["status"] == "MEASURED":
            assert all(arm["consumer_arms"][name]["status"] == "MEASURED" for name in EXPECTED_CONSUMER_ARMS)
        else:
            assert arm["blocker"]["reason"]
            assert all(arm["consumer_arms"][name]["status"] == "BLOCKED" for name in EXPECTED_CONSUMER_ARMS)


def test_each_arm_can_fail_probe_is_explicit() -> None:
    receipt = load_receipt()
    assert set(receipt["can_fail_controls"]) == set(EXPECTED_LABELS)
    for arm in receipt["arms"]:
        probe = receipt["can_fail_controls"][arm["label"]]
        assert probe["attempted"] is (arm["status"] == "MEASURED")
        if arm["status"] == "MEASURED":
            assert probe["kind"] == "mutate-real-memory-arm-target-share-to-zero"
            assert probe["mutated_share_along_target"] == 0.0
            assert probe["predicate_fires"] is True
        else:
            assert probe["status"] == "BLOCKED"


def test_continuity_owner_path_digest_and_mutation_contracts() -> None:
    receipt = load_receipt()
    assert {row["selector"] for row in receipt["continuity_checks"]} == EXPECTED_CONTINUITY
    assert all(row["within_tolerance"] for row in receipt["continuity_checks"])
    assert receipt["declared"]["timing_stripping"]["clock_leaf_keys"] == sorted(runner.TIMING_KEYS)
    assert receipt["declared"]["timing_stripping"]["derived_clock_keys"] == []
    assert runner.verify_receipt(receipt)["content_digest_matches"] is True
    mutated = copy.deepcopy(receipt)
    mutated["declared"]["hold_horizon_ticks"] += 1
    assert runner.content_digest(mutated) != receipt["content_digest"]


def test_deterministic_rebuild_and_runtime_are_recorded() -> None:
    receipt = load_receipt()
    rebuild = receipt["deterministic_rebuild"]
    assert rebuild["attempted"] is True
    assert rebuild["temp_path"] == "<temporary>/rebuild.json"
    assert rebuild["byte_stable_body"] is True
    assert receipt["runtime_seconds"] < runner.MAX_RUNTIME_SECONDS
