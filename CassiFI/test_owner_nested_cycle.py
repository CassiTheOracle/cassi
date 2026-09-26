"""Direct tests for the owner-level nested-cycle exploration runner.

They hold the runner to the properties its receipt claims, on a compact
configuration of the same runner the receipt is produced by, so a passing run is
evidence about the real measurement rather than about a fixture:

* the factorial table is read from four measured cells, one per (rail, metric),
  and the reader fails on a table that has no ladder cell;
* the rail factor is a measured structural difference while the two rails carry
  the *same* transport under a shared metric, so a metric effect cannot be a rail
  effect in disguise;
* the measured neutral gain is rail-invariant and metric-determined, and each
  arm's gain is its own refinement rather than another arm's;
* the capacity figure is carried by the metric and moved by the rail by exactly
  zero, and the read resolves the direction the arm wrote;
* every predicate carries a can-fail control: the blank arm does not recover, the
  read-suppressed arm falls back, the unwritten direction stays under the declared
  ceiling, a further impulse moves a page digest that a read left alone, a changed
  measured number changes the receipt digest, and the declared margin predicate is
  exercised on both sides of its own threshold.

Two measurements are not repeated here. The no-drive (no-loop) control is a
no-drive hold, so its separation from the held arm grows with the hold horizon: at
the receipt's declared 16 ticks it falls well outside the recovery band, while at
this file's compact horizon it would not, and a control that cannot separate is not
evidence. The shipped-episode route comparison and the reference legs are likewise
measured by the receipt at its own declared configuration; what is asserted here is
that their blocks report an unattempted run rather than disappearing.
"""

from __future__ import annotations

import copy
import json

import numpy as np
import pytest

import run_owner_nested_cycle as nested

COMPACT = nested.OwnerNestedConfig(
    hold_horizon_ticks=1,
    include_reference_legs=False,
    include_route_continuity=False,
    include_no_loop_control=False,
)

CANONICAL_FLAT = "canonical-rail-flat-metric"
NESTED_FLAT = "nested-rail-flat-metric"
CANONICAL_LADDER = "canonical-rail-ladder-metric"
NESTED_LADDER = "nested-rail-ladder-metric"

LADDER_GATE = "ladder-geometric"


@pytest.fixture(scope="module")
def receipt() -> dict:
    return nested.build_receipt(COMPACT)


def cells(receipt: dict) -> dict:
    return {
        (row["rail"], row["metric_label"]): row for row in receipt["factorial"]["cells"]
    }


# --------------------------------------------------------------------------
# the declared table
# --------------------------------------------------------------------------
def test_the_four_declared_cells_are_all_measured(receipt):
    table = cells(receipt)
    assert set(table) == {
        (nested.CANONICAL_RAIL, "flat"),
        (nested.CANONICAL_RAIL, "ladder-1.3"),
        (nested.NESTED_RAIL, "flat"),
        (nested.NESTED_RAIL, "ladder-1.3"),
    }
    assert receipt["factorial"]["expected_cells_present"] is True
    assert len(receipt["factorial"]["cells"]) == len(nested.ARM_SPECS) - 2
    for row in table.values():
        assert row["role"] == nested.FACTORIAL_CELL
        assert row["neutral_gain_measured"] is True
        assert row["written_deposit"] > 0.0
        assert row["recovery_fraction"] > 0.0
        assert row["act_selected_item"] == nested.TARGET_ITEM_NAME


def test_an_incomplete_factor_table_is_not_a_factorial():
    rows = [
        {
            "arm": CANONICAL_FLAT,
            "rail": nested.CANONICAL_RAIL,
            "metric_label": "flat",
            "role": nested.FACTORIAL_CELL,
            "written_deposit": 1.0,
        },
        {
            "arm": NESTED_FLAT,
            "rail": nested.NESTED_RAIL,
            "metric_label": "flat",
            "role": nested.FACTORIAL_CELL,
            "written_deposit": 1.0,
        },
    ]
    assert set(nested.cells_of(rows)) == {
        (nested.CANONICAL_RAIL, "flat"),
        (nested.NESTED_RAIL, "flat"),
    }
    # the effect reader is what refuses a comparison the table cannot carry
    with pytest.raises(KeyError):
        nested.rail_metric_effects(nested.cells_of(rows), "written_deposit")


def test_the_declared_margin_predicate_can_fail_both_ways():
    assert nested.separates(0.021, 0.02) is True
    assert nested.separates(0.019, 0.02) is False
    assert nested.separates(0.02, 0.02) is True
    assert nested.separates(None, 0.02) is None


def test_the_two_rails_are_one_structural_difference(receipt):
    construction = receipt["rail_construction"]
    margin = construction["margin"]
    assert construction["the_two_rails_are_different_bodies"] is True
    assert construction["relative_frobenius_difference"] > margin
    # a rail effect must not be a metric effect in disguise
    assert construction["the_ladder_rail_carries_the_same_transport_as_the_flat_rail"]
    assert construction["the_two_inverse_mass_vectors_are_the_same"] is True
    profiles = {spec.name: nested.build_arm(spec)[0] for spec in COMPACT.arms}
    flat_rail = np.asarray(nested.rail_vector(profiles[CANONICAL_FLAT]), dtype=np.float64)
    nested_rail = np.asarray(nested.rail_vector(profiles[NESTED_FLAT]), dtype=np.float64)
    assert flat_rail.shape == nested_rail.shape
    assert not np.allclose(flat_rail, nested_rail, atol=margin)
    assert profiles[CANONICAL_FLAT].projected_transport is None
    assert profiles[NESTED_FLAT].projected_transport is not None
    assert np.array_equal(
        np.asarray(profiles[CANONICAL_FLAT].projected_inv_mass, dtype=np.float64),
        np.asarray(profiles[NESTED_FLAT].projected_inv_mass, dtype=np.float64),
    )


def test_every_arm_declares_how_it_was_built(receipt):
    construction = receipt["declared"]["factorial"]["construction"]
    assert set(construction) == set(receipt["arms"])
    for name, spec in construction.items():
        assert spec["rail"] == receipt["arms"][name]["cell"]["rail"]
        assert spec["profile_sha256"]
        assert spec["built_by"].endswith("build_metric_profile")
        assert spec["declared_rule"]
        if name in (NESTED_FLAT, NESTED_LADDER):
            # the nesting is declared, not inherited from the other rail's row
            assert spec["declared_row"] is None
            assert spec["base_rail_arrangement"] == nested.NESTED_RAIL
        else:
            assert spec["declared_row"] is not None
            assert spec["declared_row_index"] is not None
    assert construction[CANONICAL_LADDER]["metric_kind"] == LADDER_GATE
    assert construction[NESTED_LADDER]["metric_kind"] == LADDER_GATE


# --------------------------------------------------------------------------
# the field's own neutral gain, per arm
# --------------------------------------------------------------------------
def test_each_arm_measures_its_own_gain_inside_its_own_bracket(receipt):
    for name, arm in receipt["arms"].items():
        gain = arm["neutral_gain"]
        assert gain["measured"] is True, name
        value = float(gain["measured_gain"])
        low, high = (float(bound) for bound in gain["bracket"])
        assert low <= value <= high, name
        assert gain["grid_monotone"] is True, name
        assert 0.0 <= float(gain["drift_retention_at_horizon"]) <= 1.0 + 1e-9, name
        assert float(gain["tolerance"]) > 0.0, name


def test_the_measured_gain_is_rail_invariant_and_metric_determined(receipt):
    arms = receipt["arms"]
    gains = {
        name: float(arms[name]["neutral_gain"]["measured_gain"])
        for name in (CANONICAL_FLAT, NESTED_FLAT, CANONICAL_LADDER, NESTED_LADDER)
    }
    assert gains[CANONICAL_FLAT] == gains[NESTED_FLAT]
    assert gains[CANONICAL_LADDER] == gains[NESTED_LADDER]
    # the comparison can see a difference, or those equalities are vacuous
    assert abs(gains[CANONICAL_LADDER] - gains[CANONICAL_FLAT]) > COMPACT.metric_margin
    assert (
        receipt["factorial"]["effects"]["neutral_gain"]["greatest_absolute_rail_effect"]
        == 0.0
    )
    assert (
        receipt["factorial"]["effects"]["neutral_gain"]["greatest_absolute_metric_effect"]
        > COMPACT.metric_margin
    )


def test_the_gain_reading_reproduces_the_shipped_receipts_same_instrument(receipt):
    concordance = receipt["cited_gain_concordance"]
    assert concordance["available"] is True
    assert concordance["this_receipts_measured_gain"] == concordance["cited_measured_gain"]
    assert concordance["absolute_difference"] == 0.0
    assert tuple(concordance["this_receipts_bracket"]) == tuple(concordance["cited_bracket"])


# --------------------------------------------------------------------------
# the owner cycle
# --------------------------------------------------------------------------
def test_the_read_recovers_the_written_direction_and_the_blank_arm_does_not(receipt):
    band = float(receipt["declared"]["margins"]["recovery_band"])
    for row in receipt["factorial"]["cells"]:
        name = row["arm"]
        arm = receipt["arms"][name]
        read = arm["cycle"]["field_episode"]["read_on_the_held_page"]
        if abs(float(read["written_direction_recovery_fraction"]) - 1.0) > band:
            raise AssertionError(
                f"{name} recovers {read['written_direction_recovery_fraction']} "
                f"against the declared band {band}"
            )
        assert row["the_recovery_is_within_the_declared_band"] is True, name
        # the band can fail: the same read on a page this arm never wrote is empty
        assert row["blank_read_target_recovered_deposit"] == 0.0, name
        assert read["the_unwritten_direction_stays_under_the_ceiling"] is True, name
        assert (
            read["unwritten_direction_fraction_of_the_written_deposit"]
            < COMPACT.unwritten_direction_ceiling
        ), name
        assert read["repeated_read_returns_the_same_readout"] is True, name
        blank = arm["blank_control"]["act_on_the_blank_page"]
        assert float(blank["retrieval"]["retrieved_deposit"]) == 0.0, name
        assert blank["decision"]["selected_item"] != nested.TARGET_ITEM_NAME, name
        # the real act is the can-fail control for the blank act's fallback
        assert (
            arm["cycle"]["act_on_the_held_page"]["decision"]["selected_item"]
            == nested.TARGET_ITEM_NAME
        ), name


def test_the_read_suppressed_arm_falls_back(receipt):
    for name, arm in receipt["arms"].items():
        suppressed = arm["cycle"]["controls"]["read_suppressed"]
        assert suppressed["decision"]["selected_item"] != nested.TARGET_ITEM_NAME, name
        assert (
            suppressed["statistic"]["share_along_target"] < COMPACT.pursuit_margin
        ), name


def test_the_reads_move_nothing_and_the_mutation_control_moves_everything(receipt):
    for name, arm in receipt["arms"].items():
        episode = arm["cycle"]["field_episode"]
        moved = episode["digests"]["the_reads"]["moved"]
        assert moved["page_moved"] is False, name
        assert moved["workspace_state_moved"] is False, name
        assert moved["owner_state_moved"] is False, name
        assert moved["ledger_moved"] is False, name
        assert moved["the_state_digest_moved_where_the_page_digest_did_not"] is False, name
        assert moved["the_ledger_moved_where_the_page_digest_did_not"] is False, name
        mutation = arm["digest_mutation_control"]
        assert mutation["applied_work"] > 0.0, name
        assert mutation["page_moved"] is True, name
        assert mutation["workspace_state_moved"] is True, name
        assert mutation["ledger_moved"] is True, name


def test_the_owner_write_moves_the_page_the_state_and_the_ledger(receipt):
    for name, arm in receipt["arms"].items():
        moves = arm["cycle"]["field_episode"]["digests"]["the_owner_write_moves"]
        assert moves["page_sha256"] is True, name
        assert moves["workspace_state_sha256"] is True, name
        assert moves["owner_state_sha256"] is True, name
        assert moves["ledger_sha256"] is True, name
        assert moves["ledger_fields_the_write_touched"], name


def test_the_episode_moves_only_the_canonical_page_and_its_own_ledger(receipt):
    for name, arm in receipt["arms"].items():
        episode = arm["cycle"]["field_episode"]
        assert episode["clocks"]["the_episode_moves_no_evidence_clock"] is True, name
        assert episode["read_frame_path"] == nested.durability.READ_FRAME_PATH, name
        assert episode["written_item"] == nested.TARGET_ITEM_NAME, name
        touched = episode["digests"]["the_owner_write_moves"][
            "ledger_fields_the_write_touched"
        ]
        held_ledger = episode["digests"]["the_reads"]["before"]["ledger"]
        # the write's effect lands in the canonical workspace's own work account
        assert set(touched) <= set(held_ledger), name
        assert "stored_energy" in held_ledger, name


def test_the_cycle_reproduces_the_declared_loop_it_is_read_against(receipt):
    for name, arm in receipt["arms"].items():
        route = arm["cycle"]["field_episode"]["owner_route_against_the_declared_loop"]
        assert route["the_owner_route_reproduces_the_declared_loop"] is True, name
        assert route["held_page_sha256"] == route["replay_page_sha256"], name


# --------------------------------------------------------------------------
# the factor comparison
# --------------------------------------------------------------------------
def test_the_capacity_figure_is_metric_carried_and_rail_blind(receipt):
    effects = receipt["factorial"]["effects"]["written_deposit"]
    table = cells(receipt)
    assert effects["relative"] is True
    assert effects["greatest_absolute_rail_effect"] == 0.0
    assert effects["greatest_absolute_metric_effect"] > effects["margin"]
    assert effects["which_factor_separates"] == "the mass metric"
    # rail blindness is an equality of measured numbers, not of rounded output
    assert (
        table[(nested.CANONICAL_RAIL, "flat")]["written_deposit"]
        == table[(nested.NESTED_RAIL, "flat")]["written_deposit"]
    )
    assert (
        table[(nested.CANONICAL_RAIL, "ladder-1.3")]["written_deposit"]
        == table[(nested.NESTED_RAIL, "ladder-1.3")]["written_deposit"]
    )
    assert (
        table[(nested.CANONICAL_RAIL, "flat")]["written_deposit"]
        != table[(nested.CANONICAL_RAIL, "ladder-1.3")]["written_deposit"]
    )


def test_the_rail_separates_no_figure_and_the_metric_carries_the_store(receipt):
    effects = receipt["factorial"]["effects"]
    assert all(block["the_rail_separates"] is not True for block in effects.values())
    separating = {
        figure
        for figure, block in effects.items()
        if block["the_metric_separates"] is True
    }
    assert "written_deposit" in separating
    assert "drift_retention_at_horizon" in separating
    assert receipt["reading"]["the_rail_is_inert_on_every_figure"] is True
    assert receipt["reading"]["the_metric_carries_the_store"] is True


def test_every_predicate_names_a_control_that_can_fail(receipt):
    controls = receipt["factorial"]["every_predicate_has_a_can_fail_control"]
    assert controls["the_held_recovery_is_a_recovery_in_its_declared_band"]
    assert controls["the_act_lies_along_the_target"]
    assert controls["the_declared_direction_is_the_one_written"]
    assert controls["the_digests_move"]
    assert controls["the_two_rails_are_different_bodies"]


def test_the_verdict_quotes_the_measured_metric_effect(receipt):
    verdict = receipt["reading"]["verdict"]
    effect = receipt["factorial"]["effects"]["written_deposit"][
        "greatest_absolute_metric_effect"
    ]
    assert "carried by the mass metric" in verdict
    assert f"{effect:.6g}" in verdict
    assert nested.verdict_sentence(receipt) == verdict


# --------------------------------------------------------------------------
# the receipt contract
# --------------------------------------------------------------------------
def test_the_receipt_digest_covers_the_numbers_and_ignores_the_wall_clock(receipt):
    changed = copy.deepcopy(receipt)
    changed["runtime_seconds"] = float(receipt["runtime_seconds"]) + 1000.0
    changed.pop("receipt_digest")
    assert nested.receipt_digest(changed) == receipt["receipt_digest"]
    moved = copy.deepcopy(receipt)
    moved["factorial"]["cells"][0]["written_deposit"] = (
        float(moved["factorial"]["cells"][0]["written_deposit"]) + 1.0
    )
    moved.pop("receipt_digest")
    assert nested.receipt_digest(moved) != receipt["receipt_digest"]
    declared = receipt["declared"]["receipt_digest"]
    assert tuple(declared["strip_keys"]) == nested.STRIP_KEYS
    assert "sha256" in declared["definition"]


def test_the_receipt_survives_a_strict_json_round_trip(receipt):
    reloaded = json.loads(json.dumps(receipt, indent=1, sort_keys=True, allow_nan=False))
    assert reloaded["receipt_digest"] == receipt["receipt_digest"]
    assert reloaded["schema"] == nested.SCHEMA
    assert reloaded["declared"]["config"]["hold_horizon_ticks"] == COMPACT.hold_horizon_ticks


def test_a_non_finite_number_is_refused_before_publication(receipt):
    nested.assert_finite(receipt)
    with pytest.raises(ValueError):
        nested.assert_finite({"arm": {"written_deposit": float("nan")}})
    with pytest.raises(ValueError):
        nested.assert_finite({"cells": [{"recovery_fraction": float("inf")}]})


def test_the_receipt_declares_the_question_and_the_margins_it_uses(receipt):
    declared = receipt["declared"]
    assert "nested" in declared["question"]
    assert "mass metric" in declared["question"]
    assert declared["factorial"]["factors"]["rail"] == [
        nested.CANONICAL_RAIL,
        nested.NESTED_RAIL,
    ]
    margins = declared["margins"]
    assert margins["rail_margin"] == COMPACT.rail_margin
    assert margins["metric_margin"] == COMPACT.metric_margin
    assert margins["deposit_relative_margin"] == COMPACT.deposit_relative_margin
    assert all(value > 0.0 for value in margins.values() if isinstance(value, float))


def test_the_inspection_surface_is_reported_where_it_raises(receipt):
    capability = receipt["capability"]
    assert capability["rails_where_inspect_resonance_is_unusable"] == [nested.NESTED_RAIL]
    for name, entry in capability["inspect_resonance"].items():
        if entry["rail"] == nested.CANONICAL_RAIL:
            assert entry["available"] is True, name
            assert entry["matches_the_public_state_fields"] == {
                "logical_tick": True,
                "generation": True,
                "state_sha256": True,
            }, name
        else:
            assert entry["available"] is False, name
            assert "FieldIntelligenceError" in entry["failure"], name


def test_an_unattempted_block_says_so_instead_of_vanishing(receipt):
    # the shipped-episode comparison runs on the canonical-flat arm only, and only
    # when the run declares it; either way the block reports itself rather than
    # being absent, so a reader cannot confuse "not attempted" with "measured equal"
    for name, arm in receipt["arms"].items():
        continuity = arm["route_continuity"]
        assert continuity["available"] is False, name
        assert continuity["reason"], name
        no_loop = arm["no_loop_control"]
        assert no_loop["available"] is False, name
        assert no_loop["reason"], name
    assert nested.OwnerNestedConfig(include_route_continuity=True).as_dict()[
        "include_route_continuity"
    ] is True
    assert receipt["declared"]["config"]["include_route_continuity"] is False
