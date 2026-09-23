"""Focused checks for the arrangement-recall consumer-path receipt."""
from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

import run_fractal_arrangement_recall_exploration as runner
import run_fractal_geometry_exploration as geometry
from cassi_field_atlas import AtlasState, canonical_json_bytes
from cassi_field_owner import FieldIntelligenceOwner
from cassi_resonant_field import initial_workspace


def test_nested_core_shell_owner_inspection_is_canonical_json(tmp_path) -> None:
    profile = geometry.build_profile(
        geometry.arrangement_named("nested-core-shell", seed=runner.SEED),
        ports_per_pool=geometry.DEFAULT_PORTS_PER_POOL,
    )
    initial = AtlasState(resonant_workspace=initial_workspace(profile))
    with FieldIntelligenceOwner(tmp_path / "field", initial_state=initial) as owner:
        state_before = owner.state.state_sha256
        report = owner.inspect_resonance()
        encoded = canonical_json_bytes(report)
        decoded = json.loads(encoded.decode("utf-8"))
        assert decoded["edge_powers"]
        assert type(decoded["edge_powers"][0]["source"]) is int
        assert type(decoded["edge_powers"][0]["destination"]) is int
        assert owner.state.state_sha256 == state_before

RECEIPT = Path(__file__).parent / "_diag" / "fractal-arrangement-recall" / "exploration.json"


def load_receipt() -> dict:
    assert RECEIPT.exists(), f"missing receipt: {RECEIPT}"
    return json.loads(RECEIPT.read_text(encoding="utf-8"))


def test_receipt_self_check_and_digest_mutation_control() -> None:
    receipt = load_receipt()
    assert runner.verify_receipt(receipt)["content_digest_matches"] is True
    mutated = copy.deepcopy(receipt)
    mutated["declared"]["hold_horizon_ticks"] += 1
    assert runner.content_digest(mutated) != receipt["content_digest"]


def test_two_arrangements_share_the_declared_consumer_contract() -> None:
    receipt = load_receipt()
    assert [arm["label"] for arm in receipt["arms"]] == [
        "current-meaningful-helix",
        "nested-core-shell-loops",
    ]
    declared = receipt["declared"]
    assert declared["task"] == "carry the remembered target direction forward"
    assert declared["candidate_directions"] == ["root-scale", "root-detail", "left-detail"]
    assert declared["write_budget"] == pytest.approx(1e-3)
    assert declared["act_budget"] == pytest.approx(1e-3)
    assert declared["hold_horizon_ticks"] == 16
    assert all(arm["declared_consumer"] == receipt["arms"][0]["declared_consumer"] for arm in receipt["arms"])


def test_helix_measures_all_consumer_arms_and_controls() -> None:
    receipt = load_receipt()
    helix = receipt["arms"][0]
    assert helix["status"] == "MEASURED"
    arms = helix["consumer_arms"]
    assert set(arms) == {
        "A-memory-used",
        "B-identity-control-read-suppressed",
        "C-no-memory",
        "D-mismatch-control",
        "C-firing-control-policy-mutated",
    }
    assert arms["A-memory-used"]["decision"]["selected_is_the_target"] is True
    assert arms["B-identity-control-read-suppressed"]["policy"]["read_suppressed"] is True
    assert arms["B-identity-control-read-suppressed"]["decision"]["selected_is_the_target"] is False
    assert arms["C-no-memory"]["decision"]["selected_is_the_target"] is False
    assert arms["D-mismatch-control"]["decision"]["selected_is_the_target"] is False
    assert arms["C-firing-control-policy-mutated"]["policy"]["policy_mutated"] is True
    assert arms["C-firing-control-policy-mutated"]["decision"]["selected_is_the_target"] is True
    assert all(arms[name]["act"]["the_act_changes_the_page"] for name in arms)


def test_each_arrangement_has_explicit_controls_and_can_fail_probe() -> None:
    receipt = load_receipt()
    for arm in receipt["arms"]:
        controls = arm["controls"]
        for name in ("silenced", "no_memory", "mismatch", "policy_mutated"):
            assert controls[name]["attempted"] is True
        probe = receipt["can_fail_controls"][arm["label"]]
        if arm["status"] == "MEASURED":
            assert probe["status"] == "MEASURED"
            assert probe["attempted"] is True
            assert probe["predicate_fires"] is True
        else:
            assert probe["status"] == "BLOCKED"
            assert arm["blocker"]["reason"]


def test_nested_arrangement_is_measured_with_live_controls() -> None:
    receipt = load_receipt()
    nested = next(arm for arm in receipt["arms"] if arm["label"] == "nested-core-shell-loops")
    assert nested["status"] == "MEASURED"
    assert all(
        nested["controls"][name]["attempted"] is True
        and nested["controls"][name]["status"] == "MEASURED"
        for name in ("silenced", "no_memory", "mismatch", "policy_mutated")
    )
    can_fail = receipt["can_fail_controls"]["nested-core-shell-loops"]
    assert can_fail["status"] == "MEASURED"
    assert can_fail["attempted"] is True
    assert receipt["verdict"] == "MEASURED"


def test_continuity_reproduces_existing_geometry_ipr_numbers() -> None:
    receipt = load_receipt()
    checks = receipt["continuity_checks"]
    assert len(checks) >= 2
    assert all(row["within_tolerance"] for row in checks)
    assert {row["selector"] for row in checks} >= {
        "arrangements[construction.name=helix7].spectrum.ipr_median",
        "arrangements[construction.name=nested-core-shell].spectrum.ipr_median",
    }


def test_deterministic_temp_rebuild_and_bounded_runtime_are_recorded() -> None:
    receipt = load_receipt()
    rebuild = receipt["deterministic_rebuild"]
    assert rebuild["attempted"] is True
    assert rebuild["temp_path"] == "<temporary>/rebuild.json"
    assert rebuild["byte_stable_body"] is True
    assert receipt["runtime_seconds"] < runner.MAX_RUNTIME_SECONDS
