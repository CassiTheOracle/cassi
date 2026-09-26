from __future__ import annotations

import copy
import pytest

from cassi_field_atlas import canonical_json_bytes, sha256_value
from cassi_field_program import execute_semantic_program
from cassi_reality_residency import (
    HORIZONS,
    RealityResidencyCampaign,
    RealityResidencyError,
    build_reality_curriculum,
    build_reality_manifest,
    global_response_candidates,
)


def test_reality_curriculum_is_deterministic_disjoint_and_sealed() -> None:
    first = build_reality_curriculum()
    second = build_reality_curriculum()
    first_manifest = build_reality_manifest(first)
    second_manifest = build_reality_manifest(second)

    assert canonical_json_bytes(first_manifest) == canonical_json_bytes(second_manifest)
    assert first_manifest["sealed_sha256"] == sha256_value(first_manifest["sealed"])
    assert first_manifest["candidate_families_sha256"] == sha256_value(
        first_manifest["candidate_families"]
    )
    assert first_manifest["engine"]["horizons"] == list(HORIZONS)

    training_focuses = {world.focus for world in first.training}
    sealed_focuses = {
        world.focus
        for world in first.holdout + first.transfer
        if world.focus is not None
    }
    assert training_focuses.isdisjoint(sealed_focuses)

    identities = [world.world_id for world in first.all_declared_worlds]
    assert len(identities) == len(set(identities))
    assert len(first.training) == 8
    assert len(first.holdout) == 6
    assert len(first.transfer) == 4
    assert len(first.null_controls) == 2
    assert len(first.repeats) == 2

    mutated = copy.deepcopy(first_manifest["sealed"])
    mutated["prospective_worlds"][0]["deposits"][0]["x"] += 0.01
    assert sha256_value(mutated) != first_manifest["sealed_sha256"]


def test_control_search_contains_an_exact_net_zero_intervention() -> None:
    curriculum = build_reality_curriculum()
    by_multiplier = {
        multiplier: world for multiplier, world in curriculum.control_options
    }

    assert set(by_multiplier) == {0.0, -0.5, -1.0, -1.5}
    cancellation = by_multiplier[-1.0]
    baseline = by_multiplier[0.0]
    assert cancellation.net_cy == 0.0
    assert cancellation.net_ci == 0.0
    assert baseline.net_cy != 0.0
    assert baseline.net_ci != 0.0


def test_global_response_family_can_identify_cross_channel_coupling() -> None:
    candidates = {
        candidate["candidate_id"]: candidate["program"]
        for candidate in global_response_candidates()
    }
    action = {"net_cy": 2.8, "net_ci": -1.2}

    truth = execute_semantic_program(
        candidates["coupled-global-mode"],
        {},
        action=action,
    )
    assert truth["status"] == "supported"
    truth_values = truth["values"]

    for candidate_id, program in candidates.items():
        applicability = program["applicability"]
        assert applicability["action_domain"] == "any"
        assert applicability["context_domain"] == "any"
        assert applicability["interval_domain"] == "any"
        assert applicability["max_supported_horizon"] == 1
        if candidate_id == "coupled-global-mode":
            continue
        outcome = execute_semantic_program(program, {}, action=action)
        assert outcome["status"] == "supported"
        squared_error = sum(
            (
                float(outcome["values"][name])
                - float(truth_values[name])
            )
            ** 2
            for name in ("global_ey_charge", "global_ei_charge")
        ) / 2.0
        assert squared_error > 1.0e-12


def test_existing_receipt_cannot_cross_campaign_contracts(tmp_path) -> None:
    run_home = tmp_path / "reality"
    campaign = RealityResidencyCampaign(
        run_home,
        run_id="receipt-contract",
    )
    wrong_receipt = {
        "schema": "cassifi.reality-residency-receipt.v1",
        "run_id": "receipt-contract",
        "manifest_sha256": "0" * 64,
        "sealed_sha256": campaign.manifest["sealed_sha256"],
        "candidate_families_sha256": campaign.manifest[
            "candidate_families_sha256"
        ],
    }
    wrong_receipt["body_sha256"] = sha256_value(wrong_receipt)
    campaign.receipt_path.write_bytes(canonical_json_bytes(wrong_receipt))

    with pytest.raises(
        RealityResidencyError,
        match="different campaign contract",
    ):
        campaign.run()
