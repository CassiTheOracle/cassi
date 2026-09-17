"""Tests for the store addressing rank measurement.

The compact build here runs the declared measurement over three declared items
(about fifty seconds); the canonical receipt over the declared eight is checked for
schema, item count, its verdicts and its digest. Every assertion reads the receipt or
the receipt's own numbers, and the can-fail checks mutate a real measurement rather
than a fixture.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import pytest

import run_memory_store_scale as scale
import run_store_addressing_rank as rank

RECEIPT_PATH = rank.RECEIPT_PATH


def _compact_settings() -> rank.AddressingRankConfig:
    return rank.AddressingRankConfig(item_indices=(0, 1, 2))


@pytest.fixture(scope="module")
def compact() -> dict[str, Any]:
    return rank.build_receipt(_compact_settings())


@pytest.fixture(scope="module")
def canonical() -> dict[str, Any]:
    # The documented run order is runner first, then pytest, so an absent receipt
    # fails here with the command that produces it rather than reading as a broken
    # harness in a tree where the runner has simply not been run.
    assert RECEIPT_PATH.exists(), (
        f"the canonical receipt {RECEIPT_PATH} is missing; produce it from CassiFI with "
        "`python run_store_addressing_rank.py`"
    )
    return json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# part one: the rank of the deposit map at the crowded state
# --------------------------------------------------------------------------
def test_part_one_verdict_follows_only_the_measured_flags(compact: Mapping[str, Any]) -> None:
    part_one = compact["part_one"]
    verdict = str(part_one["verdict"])
    crowded_full = bool(part_one["the_crowded_state_is_full_rank"])
    reference_full = bool(part_one["the_reference_state_is_full_rank"])
    constant = bool(part_one["the_crowded_deposit_vector_is_constant_at_the_tolerance"])
    assert isinstance(constant, bool)
    if not crowded_full:
        assert "cannot carry" in verdict or "undetermined" in verdict
    elif not reference_full:
        assert "undetermined" in verdict
    elif constant:
        assert verdict.startswith("readout-only collapse"), verdict
    else:
        assert "degeneracy is in the readout cells" in verdict, verdict
        # the branch's own claim is grounded in the receipt's numbers
        separation = part_one["crowded"]["separation"]["least_item_separation"]
        assert separation is not None and float(separation) > 1.0 - rank.LOSS_ALLOWANCE


def test_part_one_reports_the_rank_and_its_floor_at_both_states(compact: Mapping[str, Any]) -> None:
    part_one = compact["part_one"]
    items = int(part_one["items"])
    for name in ("crowded", "reference"):
        reading = part_one[name]["rank"]
        tolerance = reading["tolerance"]
        assert int(reading["items"]) == items
        assert len(reading["singular_values"]) == items
        assert sorted(reading["singular_values"], reverse=True) == pytest.approx(
            reading["singular_values"]
        )
        # the declared tolerance is the larger of the measured finite-difference term
        # and the declared relative scale term, both read from this reading
        assert tolerance["tolerance"] == pytest.approx(
            max(
                float(tolerance["finite_difference_term"]),
                float(tolerance["scale_term"]),
            )
        )
        assert float(tolerance["finite_difference_term"]) == pytest.approx(
            float(rank.FLOOR_FACTOR) * float(tolerance["finite_difference_floor"])
        )
        assert float(tolerance["scale_term"]) == pytest.approx(
            float(rank.EPS_FACTOR) * max(float(value) for value in reading["singular_values"])
        )
        above = [value for value in reading["singular_values"] if value > tolerance["tolerance"]]
        assert int(reading["rank"]) == len(above)
        assert bool(reading["the_map_is_full_rank"]) == (len(above) == items)
    crowded_reading = part_one["crowded"]["rank"]
    assert crowded_reading["smallest_singular_value_against_tolerance"] == pytest.approx(
        float(crowded_reading["singular_values"][-1])
        / float(crowded_reading["tolerance"]["tolerance"])
    )


def test_the_deposit_difference_reading_separates_constancy_from_the_floor(
    compact: Mapping[str, Any],
) -> None:
    for name in ("crowded", "reference"):
        reading = compact["part_one"][name]["deposit_differences"]
        deposits = [float(value) for value in reading["deposits"]]
        differences = [
            deposits[position + 1] - deposits[position]
            for position in range(len(deposits) - 1)
        ]
        assert reading["first_differences"] == pytest.approx(differences)
        assert float(reading["greatest_first_difference"]) == pytest.approx(
            max((abs(value) for value in differences), default=0.0)
        )
        assert bool(reading["the_deposit_vector_is_constant_at_the_tolerance"]) == (
            float(reading["greatest_first_difference"]) <= float(reading["tolerance"])
        )
        assert int(reading["difference_operator_rank"]) == max(len(deposits) - 1, 0)


# --------------------------------------------------------------------------
# part two: placement, separation and the rank firing control
# --------------------------------------------------------------------------
def test_part_two_predicates_hold_on_the_compact_state(compact: Mapping[str, Any]) -> None:
    part_two = compact["part_two"]
    predicates = part_two["predicates"]
    assert predicates["the_specific_arm_is_full_rank"]
    assert predicates["the_specific_arm_separates_every_pair"]
    assert predicates["the_specific_arm_reaches_the_predicted_separation"]
    assert predicates["the_shared_arm_is_rank_deficient"]
    assert predicates["the_shared_arm_separates_no_pair"]
    assert predicates["the_duplicate_arm_has_rank_one_below_the_item_count"]
    assert predicates["the_duplicated_pair_shows_zero_separation"]
    assert predicates["the_rank_reading_fires_on_the_duplicated_placement"]
    assert part_two["item_specific_placement_restores_the_rank"]
    assert part_two["failing_predicates"] == []


def test_the_placement_arms_read_one_page_and_differ_only_by_placement(
    compact: Mapping[str, Any],
) -> None:
    part_two = compact["part_two"]
    assert part_two["the_three_arms_read_one_page"]
    arms = part_two["arms"]
    assert int(arms["specific"]["rank"]["rank"]) == int(arms["specific"]["rank"]["items"])
    assert int(arms["shared"]["rank"]["rank"]) == 1
    assert int(arms["duplicate"]["rank"]["rank"]) == int(
        arms["duplicate"]["rank"]["items"]
    ) - 1
    # the shared arm is the declared structural control: its own σ_2..N sit at or
    # below its tolerance, which is the rank one it reports
    shared = arms["shared"]["rank"]
    assert all(
        float(value) <= float(shared["tolerance"]["tolerance"])
        for value in shared["singular_values"][1:]
    )
    # the least separated specific-arm pair is the predicted one, the least shared-arm
    # pair is at the floor
    assert float(arms["specific"]["separation"]["least_item_separation"]) >= (
        1.0 - float(rank.LOSS_ALLOWANCE)
    )
    assert float(arms["shared"]["separation"]["greatest_item_separation"]) <= float(
        rank.CONTRAST_FLOOR
    )
    assert float(arms["duplicate"]["separation"]["least_item_separation"]) == pytest.approx(
        0.0, abs=float(rank.CONTRAST_FLOOR)
    )


def test_the_duplicated_placement_makes_its_two_rows_identical(
    compact: Mapping[str, Any],
) -> None:
    """The control is structural in the map, not only in the predicate."""

    arms = compact["part_two"]["arms"]
    specific = arms["specific"]
    duplicate = arms["duplicate"]
    names = list(specific["map"]["item_names"])
    first, second = names[0], names[1]
    left = names.index(first)
    right = names.index(second)

    def normalized(arm: Mapping[str, Any]) -> np.ndarray:
        matrix = np.asarray(arm["map"]["matrix"], dtype=np.float64)
        diagonal = float(np.mean(np.diag(matrix)))
        return matrix / diagonal

    specific_rows = normalized(specific)
    duplicate_rows = normalized(duplicate)
    duplicated_difference = float(
        np.max(np.abs(duplicate_rows[left] - duplicate_rows[right]))
    )
    specific_difference = float(np.max(np.abs(specific_rows[left] - specific_rows[right])))
    assert duplicated_difference <= float(rank.CONTRAST_FLOOR)
    assert specific_difference >= 1.0 - float(rank.LOSS_ALLOWANCE)
    # and the duplicated pair's columns are identical too: the shared placement cannot
    # tell the two probes apart either
    assert float(
        np.max(np.abs(duplicate_rows[:, left] - duplicate_rows[:, right]))
    ) <= float(rank.CONTRAST_FLOOR)


def test_the_separation_predicate_can_fail(compact: Mapping[str, Any]) -> None:
    """Can-fail control: duplicating a row in the specific map must flip the predicate."""

    settings = _compact_settings()
    arm = compact["part_two"]["arms"]["specific"]
    declared = dict(arm["map"])
    matrix = np.asarray(declared["matrix"], dtype=np.float64).copy()
    accepted = rank.separation_reading(declared, settings)
    assert accepted["every_item_pair_is_distinguishable"]
    matrix[1] = matrix[0]
    mutated = rank.separation_reading({**declared, "matrix": matrix.tolist()}, settings)
    assert not mutated["every_item_pair_is_distinguishable"]
    duplicated = [
        pair
        for pair in mutated["item_pairs"]
        if {pair["left"], pair["right"]} == {declared["item_names"][0], declared["item_names"][1]}
    ]
    assert duplicated and float(duplicated[0]["separation"]) <= float(rank.CONTRAST_FLOOR)
    # merging one row into another removes exactly the two ordered pairs between them
    # from the distinguishable set, whatever the item count
    assert int(mutated["distinguishable_item_pairs"]) == int(
        accepted["distinguishable_item_pairs"]
    ) - 2


def test_a_zero_work_probe_is_rejected_and_moves_nothing(compact: Mapping[str, Any]) -> None:
    zero = compact["part_two"]["arms"]["specific"]["zero_probe_map"]
    assert zero is not None
    assert zero["zero_probe"] and float(zero["amplitude"]) == 0.0
    assert zero["zero_work_probes_are_rejected"]
    assert all(
        not probe["write"]["accepted"] for probe in zero["probes"]
    ), [probe["write"] for probe in zero["probes"]]
    assert max(
        (abs(float(value)) for row in zero["matrix"] for value in row), default=0.0
    ) == 0.0
    assert float(compact["part_two"]["arms"]["specific"]["zero_probe_greatest_response"]) == 0.0


def test_every_probe_in_a_map_is_an_owner_episode_on_the_same_page(
    compact: Mapping[str, Any],
) -> None:
    arm = compact["part_two"]["arms"]["specific"]
    page = arm["map"]["probe_page_sha256"]
    assert len(arm["map"]["probes"]) == len(arm["map"]["matrix"])
    assert all(probe["page_moved"] for probe in arm["map"]["probes"])
    assert all(
        bool(probe["write"]["accepted"]) for probe in arm["map"]["probes"]
    )
    assert all(
        float(probe["write"]["applied_work"]) > 0.0 for probe in arm["map"]["probes"]
    )
    # each probe starts from the same unmodified page, so the sweep's page address is
    # the crowded page the arms were built on
    assert page == compact["part_two"]["crowded_page_sha256"]
    assert page == arm["page"]["written_page_sha256"]


def test_the_reused_floor_is_declared_and_each_arm_scales_its_own(
    compact: Mapping[str, Any],
) -> None:
    arms = compact["part_two"]["arms"]
    specific_tolerance = arms["specific"]["rank"]["tolerance"]
    measured_floor = float(specific_tolerance["finite_difference_floor"])
    assert "own two probe works" in str(specific_tolerance["finite_difference_floor_source"])
    for name in ("shared", "duplicate"):
        tolerance = arms[name]["rank"]["tolerance"]
        assert "reused" in str(tolerance["finite_difference_floor_source"])
        assert float(tolerance["finite_difference_floor"]) == measured_floor
        assert float(tolerance["scale_term"]) == pytest.approx(
            float(rank.EPS_FACTOR)
            * float(arms[name]["map"]["largest_singular_value"])
        )
    assert float(arms["shared"]["rank"]["tolerance"]["scale_term"]) != pytest.approx(
        float(specific_tolerance["scale_term"])
    )


# --------------------------------------------------------------------------
# controls on the surfaces around the measurement
# --------------------------------------------------------------------------
def test_the_blank_page_reads_nothing_and_is_not_the_crowded_page(
    compact: Mapping[str, Any],
) -> None:
    blank = compact["blank_page_reads"]
    assert blank["the_blank_page_reads_nothing"]
    assert float(blank["greatest_read"]) == 0.0
    assert all(float(value) == 0.0 for value in blank["readings"].values())
    assert blank["page_sha256"] != compact["part_two"]["crowded_page_sha256"]


def test_the_arms_run_at_the_declared_budget_and_the_page_moves(
    compact: Mapping[str, Any],
) -> None:
    for name, arm in compact["part_two"]["arms"].items():
        page = arm["page"]
        assert page["the_writes_move_the_page"], name
        assert page["blank_page_sha256"] != page["written_page_sha256"]
        for write in page["writes"].values():
            assert bool(write["accepted"]), name
            assert float(write["requested_work"]) == pytest.approx(float(rank.PROBE_BUDGET))
    part_one = compact["part_one"]
    assert float(part_one["crowded"]["state"]["hold_horizon_ticks"]) == float(
        rank.HOLD_TICKS
    )
    assert part_one["crowded"]["state"]["owner_route_reproduces_the_declared_loop"]


# --------------------------------------------------------------------------
# the receipt: digest convention and the canonical full-item artifact
# --------------------------------------------------------------------------
def test_the_digest_recomputes_and_the_strip_rule_is_real(compact: Mapping[str, Any]) -> None:
    body = json.loads(json.dumps(compact))
    assert scale.receipt_digest(body) == body["receipt_digest"]
    changed = json.loads(json.dumps(body))
    changed["part_two"]["arms"]["specific"]["rank"]["singular_values"][0] = (
        float(changed["part_two"]["arms"]["specific"]["rank"]["singular_values"][0]) + 1.0
    )
    assert scale.receipt_digest(changed) != body["receipt_digest"]
    clocked = json.loads(json.dumps(body))
    clocked["part_two"]["arms"]["specific"]["page"]["elapsed_seconds"] = 12.5
    clocked["part_two"]["arms"]["specific"]["page"]["current_manifest_sha256"] = "0" * 64
    assert scale.receipt_digest(clocked) == body["receipt_digest"]
    assert "elapsed_seconds" in scale.STRIP_KEYS
    assert "current_manifest_sha256" in scale.STRIP_KEYS
    assert set(compact["declared"]["content_digest_strip_keys"]) == set(scale.STRIP_KEYS)


def test_the_receipt_refuses_non_finite_numbers(compact: Mapping[str, Any]) -> None:
    assert compact["receipt_digest"]
    scale.assert_finite(compact)
    with pytest.raises(ValueError):
        scale.assert_finite({"value": float("nan")})


def test_the_canonical_receipt_is_the_declared_item_set(canonical: Mapping[str, Any]) -> None:
    assert canonical["schema"] == rank.SCHEMA
    body = {key: value for key, value in canonical.items() if key != "receipt_digest"}
    assert scale.receipt_digest(body) == canonical["receipt_digest"]
    part_one = canonical["part_one"]
    assert int(part_one["items"]) == len(rank.ITEM_INDICES)
    assert int(part_one["crowded"]["rank"]["items"]) == len(rank.ITEM_INDICES)
    assert canonical["part_two"]["the_three_arms_read_one_page"]
    reading = canonical["reading"]
    # every declared decision predicate holds in the reported run
    assert all(bool(value) for value in reading["verdicts"].values()), reading["verdicts"]
    # the measured flags are the reported run's own values: the crowded map is full
    # rank and the deposit vector is measured not to be constant at this state
    flags = reading["measured_flags"]
    assert flags["the_crowded_state_is_full_rank"] is True
    assert flags["the_reference_state_is_full_rank"] is True
    assert flags["the_crowded_deposit_vector_is_constant_at_the_tolerance"] is False
    assert flags["the_verdict_locates_the_degeneracy_outside_the_map"] is True
    assert flags["the_verdict_is_a_store_limitation"] is False
    assert canonical["declared"]["config"]["item_indices"] == list(rank.ITEM_INDICES)
    assert canonical["declared"]["config"]["probe_budget"] == pytest.approx(
        float(rank.PROBE_BUDGET)
    )
    assert float(canonical["runtime_seconds"]) > 0.0
