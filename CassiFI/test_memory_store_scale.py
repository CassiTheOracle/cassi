"""Direct tests for the memory-store-scale runner.

They hold the runner to the properties its receipt claims: the owner write act is
destructive and the drive acts are not, the coupled realization's readout movement
is attributable to the declared relation rather than to the input code path (the
shipped identity realization is the control that must stay inert), the unwritten
page's readout movement does not depend on the memory, the store recovers every
declared item while the consumer acts round after round, the cross-item read
measure separates a written item from an unwritten one and leaks nothing, the
identity control still separates at the end of use, and the receipt digest covers
the measured body.

Every number is read from one compact receipt of the same runner the full receipt
is produced by, so a passing run is evidence about the real measurement rather
than about a fixture.
"""

from __future__ import annotations

import copy

import pytest

from run_memory_store_scale import (
    CLOCK_DERIVED_KEYS,
    CLOCK_LEAF_KEYS,
    LEAKAGE_SEPARATION_FACTOR,
    READ_LEAKAGE_ALLOWANCE,
    StoreScaleConfig,
    build_receipt,
    receipt_digest,
)
from run_memory_consumer_path import (
    PURSUIT_MARGIN,
    READ_FLOOR_FRACTION,
    SEPARATION_MARGIN,
)

COMPACT = StoreScaleConfig(
    part_a=True,
    part_b=True,
    part_a_item_index=0,
    item_indices=(0, 1, 2),
    rounds=2,
    hold_horizon_ticks=2,
    instrument_values=(-2.0, 2.0),
    neutrality_probe_items=(0,),
)

# Declared separation for the can-fail control on the drift instrument: on the
# compact configuration the never-acted cells move by ~6.7e-16 while the items the
# consumer has already acted on sit at ~2.0 of their held read, so the band below
# (0.05, the runner's own declared drift allowance) is passed by the never-acted
# cells and failed by the acted ones. A measurement that could not tell the two
# apart would fail this test.
DRIFT_BAND = float(StoreScaleConfig().read_drift_allowance)


@pytest.fixture(scope="module")
def receipt():
    return build_receipt(COMPACT)


def test_the_owner_write_act_is_destructive_and_the_drive_acts_are_not(receipt) -> None:
    arms = receipt["part_a"]["arms"]
    allowance = float(receipt["declared"]["config"]["memory_read_relative_allowance"])

    write = arms["A1-owner-write-act"]
    assert write["snapshots"]["moved"]["page_moved"] is True
    assert float(write["memory_read"]["relative_difference"]) > allowance
    assert write["memory_read"]["the_stored_memory_is_unchanged"] is False
    assert float(write["readout"]["movement"]) != 0.0

    for name in ("A2-owner-drive-act", "C1-drive-on-an-unwritten-page"):
        arm = arms[name]
        assert abs(float(arm["readout"]["movement"])) > 0.0
        assert arm["snapshots"]["moved"]["page_moved"] is False
        assert arm["snapshots"]["moved"]["workspace_state_moved"] is False
        assert arm["memory_read"]["the_stored_memory_is_unchanged"] is True

    coupled = arms["A3-coupled-drive-act"]
    assert abs(float(coupled["readout"]["movement"])) > 0.0
    moved = coupled["snapshots"]["moved"]
    assert moved["page_moved"] is False
    assert moved["workspace_state_moved"] is False
    assert moved["owner_state_moved"] is False
    assert moved["owner_ledger_moved"] is False
    assert coupled["memory_read"]["the_stored_memory_is_unchanged"] is True


def test_the_coupled_act_is_attributable_to_the_declared_relation(receipt) -> None:
    arm = receipt["part_a"]["arms"]["A3-coupled-drive-act"]
    control = arm["controls"]["shipped_relation_is_inert"]
    allowance = float(
        receipt["declared"]["config"]["transceiver_settings"]["authority_allowance"]
    )

    coupled_movement = abs(float(arm["readout"]["movement"]))
    shipped_movement = abs(float(control["readout_movement"]))
    assert coupled_movement > allowance
    assert shipped_movement <= allowance
    assert coupled_movement > shipped_movement
    assert control["the_coupled_row_exceeds_the_allowance"] is True
    assert control["the_shipped_row_is_inert"] is True
    assert (
        float(arm["realizations"]["coupled"]["authority"]["authority_window_average_spread"])
        > allowance
    )
    assert (
        float(arm["realizations"]["shipped"]["authority"]["authority_window_average_spread"])
        <= allowance
    )


def test_the_drive_readout_does_not_depend_on_the_memory(receipt) -> None:
    arms = receipt["part_a"]["arms"]
    written = arms["A2-owner-drive-act"]
    unwritten = arms["C1-drive-on-an-unwritten-page"]

    # The same act on a page nothing was written to moves the readout by the same
    # amount, so the readout movement is a property of the act and not of the
    # stored memory.
    assert abs(float(unwritten["readout"]["movement"])) == pytest.approx(
        abs(float(written["readout"]["movement"])), rel=1e-9
    )
    # And on that page the stored memory's own read is zero on both sides.
    for side in ("before", "after"):
        assert float(unwritten["memory_read"][side]["recovered_deposit"]) == 0.0
    assert float(written["memory_read"]["before"]["recovered_deposit"]) > 0.0
    assert written["blank_page_sha256"] != written["snapshots"]["before"]["page_sha256"]


def test_the_store_recovers_every_item_and_the_drift_instrument_fires(receipt) -> None:
    matrix = receipt["part_b"]["matrix"]
    store = receipt["part_b"]["store"]

    assert store["owner_route_against_the_declared_loop"][
        "the_owner_route_reproduces_the_declared_loop"
    ] is True
    assert int(store["drive_calls"]) > 0
    assert store["held_page_sha256"] != store["post_write_page_sha256"]
    assert float(matrix["recovery_at_horizon_min"]) >= float(
        receipt["declared"]["config"]["read_recovery_allowance"]
    )
    assert matrix["page_moved_in_every_round"] is True

    # The never-acted cells stay inside the declared band while the cells of the
    # items already acted on leave it: the band is not vacuous.
    greatest_never_acted = float(matrix["greatest_never_acted_read_drift"])
    assert greatest_never_acted <= DRIFT_BAND
    acted_drift = max(
        abs(float(ratio) - 1.0)
        for row in matrix["drift_rows"]
        for item, ratio in row["ratios"].items()
        if item not in row["never_acted_items"]
    )
    assert acted_drift > DRIFT_BAND
    assert len(matrix["recovery_matrix"]) == int(matrix["rounds"]) + 1


def test_cross_item_leakage_is_measured_where_the_content_is_known(receipt) -> None:
    leakage = receipt["part_b"]["leakage"]
    item_names = leakage["item_names"]

    assert len(leakage["cells"]) == len(item_names)
    assert leakage["greatest_off_diagonal_read"] is not None
    assert float(leakage["greatest_off_diagonal_read"]) <= READ_LEAKAGE_ALLOWANCE
    assert float(leakage["least_diagonal_recovery"]) >= READ_FLOOR_FRACTION
    assert leakage["the_store_leaks_nothing_across_items"] is True
    assert leakage[
        "the_leakage_measure_separates_a_written_item_from_an_unwritten_one"
    ] is True

    # The same read path returns the full deposit when the item is present, which is
    # what makes the off-diagonal zeros a measurement rather than a dead instrument.
    for witness, row in leakage["cells"].items():
        assert row is not None
        assert float(row[witness]) == pytest.approx(1.0, rel=1e-9)
    # A page holding one item reports no other item, and a page holding nothing
    # reports nothing on any direction.
    assert len(leakage["pages"]) == len(item_names)
    assert all(
        page["the_write_moves_the_page"] is True for page in leakage["pages"].values()
    )
    assert (
        float(leakage["unwritten_page_read_relative_to_the_mean_deposit"])
        <= READ_LEAKAGE_ALLOWANCE
    )
    assert leakage["the_unwritten_page_reads_nothing"] is True
    if leakage["measured_separation_factor"] is not None:
        assert float(leakage["measured_separation_factor"]) >= LEAKAGE_SEPARATION_FACTOR


def test_the_identity_control_still_separates_after_the_rounds(receipt) -> None:
    identity = receipt["part_b"]["identity_control"]

    assert identity["the_two_arms_start_from_a_byte_identical_page"] is True
    normal_share = float(identity["normal"]["share_along_the_queried_direction"])
    assert normal_share >= PURSUIT_MARGIN
    assert float(identity["suppressed"]["share_along_the_queried_direction"]) < PURSUIT_MARGIN
    assert identity["the_normal_arm_pursues_the_queried_direction"] is True
    assert identity["the_suppressed_arm_does_not"] is True
    assert float(identity["share_difference"]) >= SEPARATION_MARGIN
    assert identity["the_control_still_separates_at_the_end_of_use"] is True


def test_the_user_predicates_hold_and_the_probed_gain_is_not_vacuous(receipt) -> None:
    part_b = receipt["part_b"]

    assert all(part_b["verdicts"].values())
    assert all(receipt["part_a"]["verdicts"].values())
    assert float(part_b["gain"]["refinement"]["measured_gain"]) == pytest.approx(
        0.02734375, rel=1e-9
    )
    # A verdict over an empty probe set is vacuous, so the compact configuration
    # declares a probed item and the test holds it to being measured.
    probes = part_b["gain"]["neutrality_probes"]
    assert len(probes) == len(COMPACT.neutrality_probe_items) > 0
    for probe in probes.values():
        assert probe["the_measured_gain_is_neutral_on_this_items_page"] is True
        assert float(probe["retention_at_the_measured_gain"]) >= float(
            probe["retention_with_no_drive"]
        )


def test_receipt_digest_is_deterministic_and_covers_the_measurements(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    assert receipt_digest(body) == receipt["receipt_digest"]

    for mutate in (
        lambda value: value["part_a"]["arms"]["A1-owner-write-act"]["readout"].__setitem__(
            "movement", 123.0
        ),
        lambda value: value["part_b"]["matrix"].__setitem__(
            "greatest_never_acted_read_drift", 123.0
        ),
        lambda value: value["part_b"]["leakage"].__setitem__(
            "greatest_off_diagonal_read", 123.0
        ),
        lambda value: value["part_b"]["identity_control"].__setitem__(
            "share_difference", 123.0
        ),
        lambda value: value["part_a"]["arms"]["A2-owner-drive-act"]["snapshots"][
            "moved"
        ].__setitem__("owner_ledger_moved", False),
    ):
        mutated = copy.deepcopy(body)
        mutate(mutated)
        assert receipt_digest(mutated) != receipt["receipt_digest"]


def test_the_digest_strips_the_clock_leaves_and_what_derives_from_them(receipt) -> None:
    body = {key: value for key, value in receipt.items() if key != "receipt_digest"}
    declared = body["declared"]
    assert set(CLOCK_LEAF_KEYS) | set(CLOCK_DERIVED_KEYS) <= set(
        declared["content_digest_strip_keys"]
    )

    def at(root, path):
        node = root
        for step in path:
            node = node[step]
        return node

    # A clock leaf and a clock-derived digest both differ between two identical
    # runs, so a digest that covered them would not be reproducible; changing them
    # must leave this receipt's digest where it is.
    mutations = (
        (("part_a", "arms", "A2-owner-drive-act", "transceiver_receipt"), "elapsed_seconds", 12345.0),
        (("part_a", "arms", "A2-owner-drive-act", "snapshots", "before"), "owner_ledger_sha256", "0" * 64),
        (("part_b", "store", "snapshot_after_the_hold"), "owner_ledger_sha256", "0" * 64),
        ((), "runtime_seconds", 12345.0),
    )
    for path, key, value in mutations:
        assert key in at(body, path)
        mutated = copy.deepcopy(body)
        at(mutated, path)[key] = value
        assert receipt_digest(mutated) == receipt["receipt_digest"], (path, key)

    # And the movement booleans computed from those digests are still covered: the
    # strip rule removes the clock-contaminated value, not the measurement.
    assert receipt["part_a"]["arms"]["A2-owner-drive-act"]["snapshots"]["moved"][
        "owner_ledger_moved"
    ] is True
